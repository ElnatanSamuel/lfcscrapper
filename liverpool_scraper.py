import os
import sys
import json
import re
import html
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# ==================== CONFIGURATION ====================

# 1. Reliable Liverpool FC RSS Feeds
RSS_FEEDS = [
    {
        "name": "BBC Sport (Liverpool)",
        "url": "https://feeds.bbci.co.uk/sport/football/teams/liverpool/rss.xml",
        "category": "club_news"
    },
    {
        "name": "This Is Anfield",
        "url": "https://www.thisisanfield.com/feed/",
        "category": "club_news"
    },
    {
        "name": "Liverpool Echo (LFC)",
        "url": "https://www.liverpoolecho.co.uk/all-about/liverpool-fc/?service=rss",
        "category": "club_news"
    },
    {
        "name": "Sky Sports Football",
        "url": "https://www.skysports.com/rss/12040",
        "category": "club_news"
    },
    {
        "name": "Google News (LFC Top Stories)",
        "url": "https://news.google.com/rss/search?q=Liverpool+FC+(Slot+OR+transfer+OR+injury+OR+signing+OR+match)+when:24h&hl=en-US&gl=US&ceid=US:en",
        "category": "club_news"
    },
    {
        "name": "Google News (Tier 1 & Transfers)",
        "url": "https://news.google.com/rss/search?q=Liverpool+FC+(%22Fabrizio+Romano%22+OR+%22Paul+Joyce%22+OR+%22David+Ornstein%22+OR+%22James+Pearce%22)+when:24h&hl=en-US&gl=US&ceid=US:en",
        "category": "tier1_transfers"
    }
]

# 2. Target Public Telegram Channels (without @)
TELEGRAM_CHANNELS = [
    "liverpoolfc_news",
    "lfc_fanpage",
    "LFCTransfers",
    "fabrizioromanotg",
    "anfieldpulse"
]

# 3. Tier 1 & Reliable Liverpool Journalists
TIER_1_JOURNALISTS = [
    "fabrizio romano", "paul joyce", "david ornstein", "james pearce",
    "neil jones", "melissa reddy", "lewis steele", "ian doyle", "chris bascombe"
]

# 4. High-Priority Transfer & Breaking Keywords
TRANSFER_KEYWORDS = [
    "here we go", "agreement", "fee agreed", "bid", "medical", "contract",
    "signing", "verbal agreement", "transfer", "done deal", "clause",
    "negotiations", "personal terms", "official announcement", "confirmed"
]

IRRELEVANT_PATTERNS = [
    "crypto", "casino", "betting tips", "1xbet", "fixed match", "forex", "giveaway"
]

SEEN_NEWS_FILE = "seen_news.json"
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "ElnatanSamuel/liverpool-scraper")

# ==================== HELPER FUNCTIONS ====================

def load_seen_news():
    if os.path.exists(SEEN_NEWS_FILE):
        try:
            with open(SEEN_NEWS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_news(seen_ids):
    seen_list = list(seen_ids)[-1000:]
    with open(SEEN_NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list, f, indent=2)

def is_spam_or_irrelevant(text):
    text_lower = text.lower()
    return any(p in text_lower for p in IRRELEVANT_PATTERNS)

def classify_item(title, snippet="", source=""):
    combined = f"{title} {snippet} {source}".lower()
    is_tier1 = any(j in combined for j in TIER_1_JOURNALISTS)
    is_transfer = any(k in combined for k in TRANSFER_KEYWORDS)
    if is_tier1 or ("here we go" in combined) or (is_transfer and "liverpool" in combined):
        return "tier1_transfers"
    return "club_news"

# ==================== SCRAPING MODULES ====================

def scrape_rss_feeds():
    news_items = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for feed in RSS_FEEDS:
        try:
            print(f"Fetching RSS: {feed['name']}...")
            res = requests.get(feed["url"], headers=headers, timeout=12)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.content, "xml")
            items = soup.find_all("item") or soup.find_all("entry")

            for item in items[:10]:
                title_node = item.find("title")
                link_node = item.find("link")
                desc_node = item.find("description") or item.find("summary")

                if not title_node or not title_node.text:
                    continue

                title = title_node.text.strip()
                link = ""
                if link_node:
                    link = link_node.text.strip() or link_node.get("href", "").strip()

                raw_desc = desc_node.text.strip() if desc_node and desc_node.text else ""
                clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator=" ").strip()

                if not link or is_spam_or_irrelevant(title + " " + clean_desc):
                    continue

                if "liverpool" not in (title + " " + clean_desc).lower() and "lfc" not in title.lower():
                    continue

                category = classify_item(title, clean_desc, feed["name"])
                if feed.get("category") == "tier1_transfers":
                    category = "tier1_transfers"

                news_items.append({
                    "id": f"rss_{hash(link)}",
                    "category": category,
                    "source": feed["name"],
                    "title": title,
                    "url": link,
                    "snippet": clean_desc[:250] + ("..." if len(clean_desc) > 250 else "")
                })
        except Exception as e:
            print(f"Notice: Error fetching {feed['name']}: {e}")

    print(f"-> Collected {len(news_items)} articles from RSS Feeds.")
    return news_items

def scrape_reddit_lfc_hub():
    reddit_items = []
    url = "https://www.reddit.com/r/LiverpoolFC/new.json?limit=30"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LFCNewsDigestBot/2.0"}

    try:
        print("Fetching Reddit /r/LiverpoolFC Aggregator (Twitter/X & Tier 1 Tracker)...")
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            posts = res.json().get("data", {}).get("children", [])
            for p in posts:
                post = p.get("data", {})
                title = post.get("title", "").strip()
                flair = str(post.get("link_flair_text") or "").strip()
                post_url = post.get("url", "")
                permalink = f"https://reddit.com{post.get('permalink', '')}"
                is_stickied = post.get("stickied", False)
                selftext = post.get("selftext", "")

                if not title or is_stickied or is_spam_or_irrelevant(title):
                    continue

                is_twitter = "twitter.com" in post_url or "x.com" in post_url
                target_url = post_url if is_twitter or "http" in post_url else permalink

                flair_lower = flair.lower()
                is_tier = any(t in flair_lower for t in ["tier 1", "tier 2", "official", "reliable", "breaking"])
                category = "tier1_transfers" if is_tier else classify_item(title, selftext, flair)
                source_label = f"Twitter/X ({flair})" if is_twitter and flair else (f"Reddit [{flair}]" if flair else "r/LiverpoolFC")

                reddit_items.append({
                    "id": f"reddit_{post.get('id')}",
                    "category": category,
                    "source": source_label,
                    "title": title,
                    "url": target_url,
                    "snippet": selftext[:200].strip() + "..." if selftext else ""
                })
    except Exception as e:
        print(f"Notice: Error fetching Reddit LFC hub: {e}")

    print(f"-> Collected {len(reddit_items)} items from Reddit & Twitter Aggregator.")
    return reddit_items

def scrape_telegram_channels():
    telegram_news = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for channel in TELEGRAM_CHANNELS:
        url = f"https://t.me/s/{channel}"
        try:
            print(f"Checking Telegram Channel: @{channel}...")
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            messages = soup.find_all("div", class_="tgme_widget_message")

            for msg in messages[-20:]:
                msg_id = msg.get("data-post")
                text_div = msg.find("div", class_="tgme_widget_message_text")
                if not text_div:
                    continue

                raw_text = text_div.get_text(separator="\n").strip()
                if not raw_text or is_spam_or_irrelevant(raw_text):
                    continue

                raw_lower = raw_text.lower()
                is_lfc = any(k in raw_lower for k in ["liverpool", "lfc", "anfield", "slot", "salah", "van dijk", "alisson", "trent"])
                if not is_lfc and channel != "liverpoolfc_news":
                    continue

                first_line = raw_text.split("\n")[0][:100].strip()
                category = "tier1_transfers" if ("fabrizio" in channel.lower() or any(k in raw_lower for k in ["here we go", "done deal"])) else "social_telegram"

                telegram_news.append({
                    "id": f"tg_{msg_id}",
                    "category": category,
                    "source": f"Telegram (@{channel})",
                    "title": first_line if first_line else f"Update from @{channel}",
                    "url": f"https://t.me/{msg_id}",
                    "snippet": raw_text[:280].strip() + ("..." if len(raw_text) > 280 else "")
                })
        except Exception as e:
            print(f"Notice: Error reading Telegram channel @{channel}: {e}")

    print(f"-> Collected {len(telegram_news)} posts from Telegram Channels.")
    return telegram_news

# ==================== TELEGRAM BOT DISPATCH ====================

def send_telegram_digest(news_items):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing.")
        return

    tier1_items = [n for n in news_items if n.get("category") == "tier1_transfers"]
    club_items = [n for n in news_items if n.get("category") == "club_news"]
    social_items = [n for n in news_items if n.get("category") == "social_telegram"]

    sections = []
    if tier1_items:
        sections.append(("🔥 <b>BREAKING & TIER 1 TRANSFERS</b>", tier1_items))
    if club_items:
        sections.append(("📰 <b>LFC CLUB & MATCH NEWS</b>", club_items))
    if social_items:
        sections.append(("💬 <b>TELEGRAM & SOCIAL UPDATES</b>", social_items))

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    date_str = datetime.now(timezone.utc).strftime("%A, %b %d, %Y")

    for section_title, section_list in sections:
        batch_size = 5
        for i in range(0, len(section_list), batch_size):
            batch = section_list[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(section_list) + batch_size - 1) // batch_size

            msg_text = f"🔴 <b>LIVERPOOL FC DIGEST</b> 🔴\n"
            msg_text += f"📅 <i>{date_str}</i>\n\n"
            msg_text += f"{section_title} <i>({batch_num}/{total_batches})</i>\n\n"

            for item in batch:
                title = html.escape(item["title"])
                source = html.escape(item["source"])
                url = html.escape(item["url"])
                snippet = html.escape(item.get("snippet", ""))

                msg_text += f"• <b>{title}</b>\n"
                msg_text += f"  🏷️ <i>{source}</i>\n"
                if snippet and snippet != title:
                    msg_text += f"  📝 {snippet}\n"
                msg_text += f"  🔗 <a href=\"{url}\">Open Article / Post</a>\n\n"

            payload = {
                "chat_id": chat_id,
                "text": msg_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }

            if section_title == sections[-1][0] and (i + batch_size >= len(section_list)):
                payload["reply_markup"] = {
                    "inline_keyboard": [
                        [
                            {"text": "⚡ Check / Scrape News Now", "url": f"https://github.com/{GITHUB_REPO}/actions"},
                            {"text": "🔴 Official LFC News", "url": "https://www.liverpoolfc.com/news"}
                        ]
                    ]
                }

            try:
                res = requests.post(api_url, json=payload, timeout=15)
                if res.status_code != 200:
                    print(f"Telegram API Error: {res.text}")
            except Exception as e:
                print(f"Error sending Telegram message: {e}")

# ==================== MAIN ====================

def main():
    print("=== Liverpool FC Daily News Scraper Starting ===")
    seen_ids = load_seen_news()

    all_news = scrape_rss_feeds() + scrape_reddit_lfc_hub() + scrape_telegram_channels()

    new_items = [n for n in all_news if n["id"] not in seen_ids]
    for item in new_items:
        seen_ids.add(item["id"])

    print(f"Total new items to dispatch: {len(new_items)}")
    if new_items:
        send_telegram_digest(new_items)
        save_seen_news(seen_ids)
    else:
        print("No new stories since last run. Everything is up to date!")

if __name__ == "__main__":
    main()
