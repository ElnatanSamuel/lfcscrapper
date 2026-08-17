🔴 Liverpool FC Daily News & Transfer Scraper
An automated daily news aggregator and Telegram digest bot built for Liverpool Football Club (LFC). It continuously monitors and compiles updates across Tier 1 Twitter/X Journalists, Reliable News Outlets (BBC, This Is Anfield, Liverpool Echo, Sky Sports), Public Telegram Channels, and Subreddit News Hubs, delivering a clean, categorized HTML digest directly to your Telegram chat.

🚀 Key Features
🔥 Tier 1 & Transfer Tracking: Prioritizes verified reporters (Paul Joyce, David Ornstein, Fabrizio Romano, James Pearce, Neil Jones, Lewis Steele) and highlights breaking transfer keywords (Here we go, Done deal, Medical, Agreement).
📰 Reliable Club News: Pulls verified articles, tactical breakdowns, press conferences, and match reports from BBC Sport, This Is Anfield, and Liverpool Echo.
💬 Public Telegram Channels: Scrapes channels like `@liverpoolfc_news`, `@lfc_fanpage`, `@fabrizioromanotg`, and `@anfieldpulse` via web preview without requiring Telegram API keys.
🐦 Twitter/X Aggregator: Tracks live Twitter/X reporting with instant deduplication.
⚡ GitHub Actions Automation: Runs on an automated daily schedule (8:00 AM & 6:00 PM EAT) and auto-saves the `seen_news.json` state.
📱 Clean HTML Telegram Formatting: Formatted with bold headings, emojis, clickable links, and interactive buttons.

📁 Repository Structure
liverpool-scraper/
├── .github/
│   └── workflows/
│       └── liverpool_digest.yml   # GitHub Actions scheduled workflow
├── liverpool_scraper.py           # Main Python scraper & Telegram dispatcher
├── requirements.txt               # Python dependencies
├── seen_news.json                 # Automatic deduplication state
└── README.md                      # Setup guide

🛠️ Step-by-Step Setup
1. Set Up Telegram Bot Credentials
Open Telegram and search for `@BotFather`.
Send `/newbot` and follow the prompts to create your bot (or use your existing `@elscrapperbot`). Copy the HTTP API Token.
Open your bot on Telegram and click Start.
Search for `@userinfobot` on Telegram and send any message to copy your numerical User ID (chat_id).
2. Configure GitHub Repository Secrets
In your GitHub repository:
Go to Settings -> Secrets and variables -> Actions -> New repository secret.
Add the following secrets:
`TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token.
`TELEGRAM_CHAT_ID`: Your numerical chat ID.
3. Enable GitHub Actions Permissions
Go to Settings -> Actions -> General.
Under Workflow permissions, select Read and write permissions (allows the workflow to commit `seen_news.json`).
Click Save.
4. Trigger Your First Scrape
Go to the Actions tab in your repository.
Select Liverpool FC Daily Digest on the left menu.
Click Run workflow -> Run workflow.
Check your Telegram chat for the formatted digest!

💻 Local Execution
To run locally on your machine:
# Clone the repository
git clone https://github.com/your-username/liverpool-scraper.git
cd liverpool-scraper

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"

# Run scraper
python liverpool_scraper.py

⚙️ Customization
Add More Telegram Channels: Open `liverpool_scraper.py` and add new channel usernames to `TELEGRAM_CHANNELS`.
Change Schedule: Edit `.github/workflows/liverpool_digest.yml` cron expression (`cron: '0 5,15 * * *'` for 8:00 AM & 6:00 PM UTC+3).
