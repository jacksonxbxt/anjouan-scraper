import asyncio
import json
import os
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PROXY_SERVER = os.environ.get("PROXY_SERVER")  # Optional: format "http://user:pass@host:port"
OUTPUT_FILE = "promo_results.json"

# Casino sites to scrape (from Anjouan register)
CASINO_SITES = [
    {"name": "Instant Casino", "url": "https://www.instantcasino.com/promotions"},
    {"name": "24Slots", "url": "https://24slots.com/promotions"},
    {"name": "PalmSlots", "url": "https://palmslots.com/promotions"},
    {"name": "Dolfwin", "url": "https://dolfwin.com/promotions"},
    {"name": "OlympusBet", "url": "https://olympusbet.com/promotions"},
    {"name": "Dream.bet", "url": "https://dream.bet/promotions"},
    {"name": "FestivalPlay", "url": "https://festivalplay.com/promotions"},
    {"name": "Bety", "url": "https://www.bety.com/bonus"},
    {"name": "Eagle777", "url": "https://eagle777.com/promotions"},
    {"name": "InterCasino", "url": "https://www.intercasino.com/en/our-casino-bonuses/"},
    {"name": "BookOfCasino", "url": "https://bookofcasino.net/promotions"},
    {"name": "VegasDukes", "url": "https://vegasdukes.com/promotions"},
    {"name": "Pinnacle Casino", "url": "https://casino.pinnacle.com/en/promotions"},
    {"name": "StarBets", "url": "https://starbets.io/bonus"},
    {"name": "Sikwin", "url": "https://sikwin.com/promotions"},
]


async def extract_promo_text(page):
    """Extract promotion-related text from the page."""
    try:
        # Wait for content to load
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)  # Extra wait for JS rendering

        # Try to extract text from common promo elements
        selectors = [
            ".promotion", ".promo", ".bonus", ".offer", ".welcome",
            "[class*='promo']", "[class*='bonus']", "[class*='offer']",
            "main", "article", ".content", "#content", ".container"
        ]

        promo_text = ""
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements[:5]:  # Limit to first 5 matches
                    text = await el.inner_text()
                    if text and len(text) > 50:
                        promo_text += text + "\n\n"
            except:
                continue

        # Fallback: get all visible text
        if not promo_text or len(promo_text) < 100:
            promo_text = await page.inner_text("body")

        # Clean up the text
        promo_text = re.sub(r'\n{3,}', '\n\n', promo_text)
        promo_text = promo_text[:5000]  # Limit length

        return promo_text
    except Exception as e:
        return f"Error extracting text: {e}"


async def extract_promos_structured(page, text):
    """Try to extract structured promo data."""
    promos = []

    # Common patterns for bonuses
    patterns = [
        r'(\d+%)\s*(?:up to|bonus|match)[^\n]*(?:€|£|\$|USD|EUR)?\s*(\d+[,.]?\d*)',
        r'(?:€|£|\$|USD|EUR)\s*(\d+[,.]?\d*)\s*(?:bonus|free|welcome)',
        r'(\d+)\s*free\s*spins',
        r'welcome\s*(?:bonus|package|offer)[^\n]*(\d+%)',
        r'(\d+x)\s*wager',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                promos.append(" ".join(match))
            else:
                promos.append(match)

    return list(set(promos))[:10]  # Dedupe and limit


async def scrape_casino(browser, casino):
    """Scrape a single casino site."""
    context_options = {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if PROXY_SERVER:
        context_options["proxy"] = {"server": PROXY_SERVER}

    context = await browser.new_context(**context_options)

    page = await context.new_page()
    result = {
        "name": casino["name"],
        "url": casino["url"],
        "status": "unknown",
        "promos": [],
        "raw_text": "",
        "scraped_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        print(f"Scraping {casino['name']}...")

        # Navigate with extended timeout for Cloudflare
        response = await page.goto(casino["url"], timeout=30000, wait_until="domcontentloaded")

        # Check for Cloudflare challenge
        content = await page.content()
        if "Just a moment" in content or "challenge" in content.lower():
            print(f"  Cloudflare challenge detected, waiting...")
            await asyncio.sleep(8)  # Wait for challenge to complete
            await page.wait_for_load_state("networkidle", timeout=20000)

        # Check for geo-block
        if "not accept players" in content.lower() or "restricted" in content.lower():
            result["status"] = "geo_blocked"
            result["raw_text"] = "Site geo-blocked for this location"
        else:
            # Extract promo text
            text = await extract_promo_text(page)
            result["raw_text"] = text
            result["promos"] = await extract_promos_structured(page, text)
            result["status"] = "success" if len(text) > 100 else "minimal_content"

        print(f"  {casino['name']}: {result['status']} - Found {len(result['promos'])} promo patterns")

    except Exception as e:
        result["status"] = "error"
        result["raw_text"] = str(e)
        print(f"  {casino['name']}: Error - {e}")

    finally:
        await context.close()

    return result


async def send_telegram(message):
    """Send message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"TG: {message[:100]}...")
        return

    import aiohttp
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message[:4000],
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        })


async def main():
    print(f"Starting promo scraper at {datetime.now(timezone.utc).isoformat()}")

    results = []

    async with async_playwright() as p:
        # Launch browser with stealth settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )

        # Scrape each casino
        for casino in CASINO_SITES:
            result = await scrape_casino(browser, casino)
            results.append(result)
            await asyncio.sleep(2)  # Be polite between requests

        await browser.close()

    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    blocked = sum(1 for r in results if r["status"] == "geo_blocked")
    errors = sum(1 for r in results if r["status"] == "error")

    summary = f"""<b>Promo Scraper Results</b>
Success: {success}/{len(results)}
Geo-blocked: {blocked}
Errors: {errors}

"""

    # Add promo highlights
    for r in results:
        if r["promos"]:
            summary += f"\n<b>{r['name']}</b>: {', '.join(r['promos'][:3])}"

    await send_telegram(summary)
    print(f"\nDone! Results saved to {OUTPUT_FILE}")
    print(f"Success: {success}, Blocked: {blocked}, Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(main())
