

import os
import sys
import json
import re
import html
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# ==================== CONFIGURATION ====================

RSS_FEEDS = [
    {"name": "BBC Sport", "url": "https://feeds.bbci.co.uk/sport/football/teams/liverpool/rss.xml"},
    {"name": "This Is Anfield", "url": "https://www.thisisanfield.com/feed/"},
    {"name": "Liverpool Echo", "url": "https://www.liverpoolecho.co.uk/all-about/liverpool-fc/?service=rss"},
    {"name": "Sky Sports", "url": "https://www.skysports.com/rss/12040"},
    {"name": "Google News (Tier 1)", "url": "https://news.google.com/rss/search?q=Liverpool+FC+(%22Fabrizio+Romano%22+OR+%22Paul+Joyce%22+OR+%22David+Ornstein%22+OR+%22James+Pearce%22)+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News (Top Stories)", "url": "https://news.google.com/rss/search?q=Liverpool+FC+(Slot+OR+transfer+OR+injury+OR+signing)+when:24h&hl=en-US&gl=US&ceid=US:en"}
]

TELEGRAM_CHANNELS = [
    "liverpoolfc_news",
    "lfc_fanpage",
    "LFCTransfers",
    "fabrizioromanotg",
    "anfieldpulse"
]

TIER_1_JOURNALISTS = [
    "fabrizio romano", "paul joyce", "david ornstein", "james pearce",
    "neil jones", "melissa reddy", "lewis steele", "chris bascombe"
]

TRANSFER_KEYWORDS = [
    "here we go", "agreement", "fee agreed", "bid", "medical", "contract",
    "signing", "verbal agreement", "transfer", "done deal", "negotiations"
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

def is_spam(text):
    spam_terms = ["crypto", "casino", "betting tips", "1xbet", "giveaway", "fixed match"]
    t = text.lower()
    return any(s in t for s in spam_terms)

# ==================== SCRAPING MODULES ====================

def scrape_all_sources():
    """Scrapes RSS feeds, Reddit/Twitter Tier tracker, and Telegram channels."""
    collected = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 1. RSS Feeds
    for feed in RSS_FEEDS:
        try:
            res = requests.get(feed["url"], headers=headers, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "xml")
                items = soup.find_all("item") or soup.find_all("entry")
                for item in items[:8]:
                    t_node = item.find("title")
                    l_node = item.find("link")
                    d_node = item.find("description") or item.find("summary")
                    if not t_node or not t_node.text:
                        continue
                    title = t_node.text.strip()
                    link = l_node.text.strip() if l_node else ""
                    desc = BeautifulSoup(d_node.text, "html.parser").get_text(separator=" ").strip() if d_node else ""
                    if is_spam(title + " " + desc):
                        continue
                    if "liverpool" in (title + " " + desc).lower() or "lfc" in title.lower():
                        collected.append({
                            "id": f"rss_{hash(link or title)}",
                            "title": title,
                            "source": feed["name"],
                            "url": link,
                            "summary": desc[:250]
                        })
        except Exception as e:
            print(f"Notice: RSS {feed['name']} error: {e}")

    # 2. Reddit /r/LiverpoolFC Hub (Twitter/X Tier Tracker)
    try:
        res = requests.get("https://www.reddit.com/r/LiverpoolFC/new.json?limit=30", headers={"User-Agent": "LFCBot/2.0"}, timeout=12)
        if res.status_code == 200:
            posts = res.json().get("data", {}).get("children", [])
            for p in posts:
                post = p.get("data", {})
                title = post.get("title", "").strip()
                flair = str(post.get("link_flair_text") or "").strip()
                url = post.get("url", "")
                selftext = post.get("selftext", "")
                if title and not post.get("stickied") and not is_spam(title):
                    source_tag = f"Twitter/X ({flair})" if ("twitter" in url or "x.com" in url) else (f"Reddit [{flair}]" if flair else "r/LiverpoolFC")
                    collected.append({
                        "id": f"reddit_{post.get('id')}",
                        "title": title,
                        "source": source_tag,
                        "url": url if "http" in url else f"https://reddit.com{post.get('permalink', '')}",
                        "summary": selftext[:200]
                    })
    except Exception as e:
        print(f"Notice: Reddit/Twitter tracker error: {e}")

    # 3. Telegram Channels
    for channel in TELEGRAM_CHANNELS:
        try:
            res = requests.get(f"https://t.me/s/{channel}", headers=headers, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                messages = soup.find_all("div", class_="tgme_widget_message")
                for msg in messages[-15:]:
                    msg_id = msg.get("data-post")
                    text_div = msg.find("div", class_="tgme_widget_message_text")
                    if not text_div:
                        continue
                    text = text_div.get_text(separator="\n").strip()
                    if text and not is_spam(text):
                        if "liverpool" in text.lower() or "lfc" in text.lower() or channel == "liverpoolfc_news":
                            first_line = text.split("\n")[0][:90].strip()
                            collected.append({
                                "id": f"tg_{msg_id}",
                                "title": first_line,
                                "source": f"Telegram (@{channel})",
                                "url": f"https://t.me/{msg_id}",
                                "summary": text[:250]
                            })
        except Exception as e:
            print(f"Notice: Telegram channel @{channel} error: {e}")

    return collected

# ==================== SUMMARY COMPOSER ====================

def generate_ai_summary(news_items):
    """Uses free Gemini API to summarize all news into concise bullet points."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None

    raw_text = ""
    for idx, item in enumerate(news_items[:30], 1):
        raw_text += f"{idx}. [{item['source']}] {item['title']}: {item['summary']} (Link: {item['url']})\n"

    prompt = f"""
You are a senior Liverpool FC football journalist.
Synthesize the following {len(news_items)} raw headlines and social reports into a single, clean, highly engaging daily briefing for Telegram in HTML format.

Rules:
1. Do NOT list 30 separate items. Combine overlapping stories into 4-6 synthesized bullet points.
2. Structure the digest into clear sections:
   🔥 <b>Transfers & Tier 1 Rumours</b>
   🏥 <b>Squad, Injuries & Press Conferences</b>
   ⚽ <b>Tactics, Matches & Club Updates</b>
   💬 <b>Social & Telegram Highlights</b>
3. Under each section, write concise bullet points (•) summarizing the key takeaway in 1-2 sharp sentences.
4. Include source attribution and hyperlinks: e.g. (via <a href=\"URL\">Source</a>).
5. Use clean HTML tags (<b>, <i>, <a>). Do NOT use markdown asterisks or backticks.
6. Keep the total length around 350-500 words so it fits in a single Telegram message.

Raw News Data:
{raw_text}
"""
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1000}
    }

    try:
        res = requests.post(api_url, json=payload, timeout=25)
        if res.status_code == 200:
            ai_text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Clean up potential code block wrappers
            ai_text = re.sub(r"^```html\s*", "", ai_text)
            ai_text = re.sub(r"^```\s*", "", ai_text)
            ai_text = re.sub(r"\s*```$", "", ai_text)
            return ai_text
        else:
            print(f"Gemini API Error: {res.text}")
    except Exception as e:
        print(f"Notice: AI synthesis error ({e}). Falling back to smart clustering.")
    return None

def generate_cluster_summary(news_items):
    """Fallback smart clusterer (pure Python) to compose bullet points across topics."""
    date_str = datetime.now(timezone.utc).strftime("%A, %b %d, %Y")
    
    transfers = []
    club_news = []
    social = []

    seen_titles = set()
    for item in news_items:
        # Deduplicate very similar titles
        clean_t = re.sub(r"[^a-zA-Z0-9\s]", "", item["title"].lower())[:40]
        if clean_t in seen_titles:
            continue
        seen_titles.add(clean_t)

        t_lower = item["title"].lower() + " " + item["summary"].lower()
        is_transfer = any(k in t_lower for k in TRANSFER_KEYWORDS) or any(j in t_lower for j in TIER_1_JOURNALISTS)
        
        if is_transfer:
            transfers.append(item)
        elif "telegram" in item["source"].lower():
            social.append(item)
        else:
            club_news.append(item)

    msg = f"🔴 <b>LIVERPOOL FC DAILY BRIEFING</b> 🔴\n"
    msg += f"📅 <i>{date_str}</i>\n"
    msg += f"📊 <i>Compiled from {len(news_items)} updates across Twitter, Outlets & Telegram</i>\n\n"

    if transfers:
        msg += f"🔥 <b>TRANSFERS & TIER 1 RUMOURS</b>\n"
        for it in transfers[:5]:
            t = html.escape(it["title"])
            s = html.escape(it["source"])
            u = html.escape(it["url"])
            msg += f"• <b>{t}</b>\n  🔗 <a href=\"{u}\">{s}</a>\n\n"

    if club_news:
        msg += f"📰 <b>CLUB NEWS & MATCH UPDATES</b>\n"
        for it in club_news[:5]:
            t = html.escape(it["title"])
            s = html.escape(it["source"])
            u = html.escape(it["url"])
            msg += f"• <b>{t}</b>\n  🔗 <a href=\"{u}\">{s}</a>\n\n"

    if social:
        msg += f"💬 <b>TELEGRAM & SOCIAL BUZZ</b>\n"
        for it in social[:3]:
            t = html.escape(it["title"])
            s = html.escape(it["source"])
            u = html.escape(it["url"])
            msg += f"• <b>{t}</b>\n  🔗 <a href=\"{u}\">{s}</a>\n\n"

    return msg

# ==================== TELEGRAM DISPATCH ====================

def send_telegram_summary(summary_html):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing!")
        return

    date_str = datetime.now(timezone.utc).strftime("%A, %b %d, %Y")
    header = f"🔴 <b>LIVERPOOL FC DAILY DIGEST</b> 🔴\n📅 <i>{date_str}</i>\n\n"
    
    if "LIVERPOOL FC" not in summary_html:
        full_text = header + summary_html
    else:
        full_text = summary_html

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": full_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "⚡ Check / Scrape Again", "url": f"https://github.com/{GITHUB_REPO}/actions"},
                    {"text": "🔴 Official LFC News", "url": "https://www.liverpoolfc.com/news"}
                ]
            ]
        }
    }

    try:
        res = requests.post(api_url, json=payload, timeout=20)
        if res.status_code != 200:
            print(f"Telegram API Error: {res.text}")
        else:
            print("Summary digest delivered successfully to Telegram!")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

# ==================== MAIN ====================

def main():
    print("=== Liverpool FC News Summarizer Starting ===")
    seen_ids = load_seen_news()

    all_items = scrape_all_sources()
    new_items = [it for it in all_items if it["id"] not in seen_ids]

    print(f"Found {len(all_items)} total stories ({len(new_items)} new).")

    if not new_items:
        print("No new news to report. Everything is up to date!")
        return

    print("Composing unified summary digest...")
    # Try AI synthesis first; fallback to smart clustering
    summary = generate_ai_summary(new_items)
    if not summary:
        summary = generate_cluster_summary(new_items)

    send_telegram_summary(summary)

    # Update seen news tracker
    for it in new_items:
        seen_ids.add(it["id"])
    save_seen_news(seen_ids)
    print("seen_news.json updated.")

if __name__ == "__main__":
    main()

