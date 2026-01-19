# Anjouan License Scraper

Scrapes the Anjouan Gaming license register and sends new licenses to Telegram.

## Setup

### 1. Create a Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID
1. Start a chat with your new bot (send any message)
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789}` - that number is your chat ID

### 3. Deploy to GitHub
1. Create a new GitHub repository
2. Push this code to it
3. Go to Settings > Secrets and variables > Actions
4. Add two secrets:
   - `TELEGRAM_BOT_TOKEN`: Your bot token
   - `TELEGRAM_CHAT_ID`: Your chat ID

### 4. Enable Actions
1. Go to the Actions tab in your repo
2. Enable workflows if prompted
3. The scraper will run every 6 hours automatically

### Manual Trigger
You can manually trigger the scraper from the Actions tab > "Scrape Anjouan Licenses" > "Run workflow"

## Local Testing
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python scraper.py
```
