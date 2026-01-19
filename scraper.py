import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
REGISTER_URL = "https://anjouangaming.com/license-register/"
SEEN_FILE = "seen_licenses.json"


def load_seen_licenses():
    """Load previously seen license numbers."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return {"licenses": [], "last_check": None}


def save_seen_licenses(data):
    """Save seen licenses to file."""
    data["last_check"] = datetime.utcnow().isoformat()
    with open(SEEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def scrape_licenses():
    """Scrape the Anjouan Gaming license register."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(REGISTER_URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    licenses = []

    # Find all table rows (the register is displayed as a table)
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 3:
                # Extract data from cells
                cell_texts = [cell.get_text(strip=True) for cell in cells]

                # Look for license number pattern (ALSI-XXXXXXXX-XXX)
                license_num = None
                operator = None
                websites = []

                for i, text in enumerate(cell_texts):
                    if re.match(r"ALSI-\d+-\w+", text):
                        license_num = text
                    elif ".com" in text or ".io" in text or ".pro" in text or ".game" in text or ".org" in text:
                        websites.append(text)
                    elif i == 0 and text and not license_num:
                        operator = text

                # Also check for links in cells
                for cell in cells:
                    links = cell.find_all("a", href=True)
                    for link in links:
                        href = link.get("href", "")
                        if href and "anjouangaming" not in href:
                            websites.append(href.replace("https://", "").replace("http://", "").rstrip("/"))

                if license_num:
                    licenses.append({
                        "license": license_num,
                        "operator": operator or "Unknown",
                        "websites": list(set(websites))
                    })

    return licenses


def send_telegram_message(message):
    """Send a message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set, printing to console:")
        print(message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    response = requests.post(url, json=payload, timeout=10)
    return response.status_code == 200


def format_license_message(license_data):
    """Format a license entry for Telegram."""
    websites = ", ".join(license_data["websites"]) if license_data["websites"] else "N/A"
    return (
        f"<b>New Anjouan License</b>\n"
        f"Operator: {license_data['operator']}\n"
        f"License: <code>{license_data['license']}</code>\n"
        f"Websites: {websites}"
    )


def main():
    print(f"Starting scrape at {datetime.utcnow().isoformat()}")

    # Load previously seen licenses
    seen_data = load_seen_licenses()
    seen_licenses = set(seen_data["licenses"])

    # Scrape current licenses
    try:
        current_licenses = scrape_licenses()
        print(f"Found {len(current_licenses)} total licenses")
    except Exception as e:
        error_msg = f"Scraping failed: {e}"
        print(error_msg)
        send_telegram_message(f"⚠️ Anjouan Scraper Error: {error_msg}")
        return

    # Find new licenses
    new_licenses = []
    for lic in current_licenses:
        if lic["license"] not in seen_licenses:
            new_licenses.append(lic)
            seen_licenses.add(lic["license"])

    print(f"Found {len(new_licenses)} new licenses")

    # Send notifications for new licenses
    if new_licenses:
        # Send summary first
        summary = f"🎰 <b>{len(new_licenses)} New Anjouan License(s) Found!</b>\n"
        summary += f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
        summary += "─" * 20
        send_telegram_message(summary)

        # Send each new license
        for lic in new_licenses:
            msg = format_license_message(lic)
            send_telegram_message(msg)
            print(f"Notified: {lic['license']}")
    else:
        print("No new licenses found")

    # Save updated seen licenses
    seen_data["licenses"] = list(seen_licenses)
    save_seen_licenses(seen_data)
    print("Done!")


if __name__ == "__main__":
    main()
