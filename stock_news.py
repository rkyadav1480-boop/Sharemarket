import os
import json
import hashlib
import asyncio
import re
import feedparser
from urllib.parse import quote_plus
from datetime import datetime
from telegram import Bot

# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("MY_CHAT_ID")

JSON_FILES = [
    "nse_history.json",
    "bullrun_history.json"
]

SENT_FILE = "sent_news.json"

# Prevents hitting Telegram limits (30 msgs/sec max) and Google blocks
MAX_CONCURRENT_STOCKS = 3 
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_STOCKS)

bot = Bot(token=BOT_TOKEN)

# =========================================================
# LOAD SENT NEWS
# =========================================================
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        try:
            SENT_NEWS = json.load(f)
        except json.JSONDecodeError:
            SENT_NEWS = {}
else:
    SENT_NEWS = {}

# =========================================================
# SAVE SENT NEWS
# =========================================================
def save_sent_news():
    with open(SENT_FILE, "w") as f:
        json.dump(SENT_NEWS, f, indent=2)

# =========================================================
# EXTRACT LATEST STOCKS (FIXED MULTI-FILE OVERWRITE)
# =========================================================
def extract_latest_stocks():
    combined_latest_stocks = []

    for file_name in JSON_FILES:
        if not os.path.exists(file_name):
            print(f"FILE NOT FOUND: {file_name}")
            continue
        try:
            with open(file_name, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"JSON ERROR {file_name}: {e}")
            continue

        # Find all valid dates within this specific file
        file_dates = []
        for key in data.keys():
            try:
                if "-" in key and len(key.split("-")[0]) == 4:
                    dt = datetime.strptime(key, "%Y-%m-%d")
                else:
                    dt = datetime.strptime(key, "%d-%m-%Y")
                file_dates.append((dt, key))
            except ValueError:
                pass

        if not file_dates:
            continue

        # Get the latest date entry specifically for THIS file
        _, file_latest_key = max(file_dates)
        values = data[file_latest_key]

        # Extract items safely into our running master list
        if isinstance(values, list) and len(values) > 0:
            if isinstance(values[0], str):
                combined_latest_stocks.extend(values)
            elif isinstance(values[0], dict):
                for item in values:
                    stock = item.get("stock")
                    if stock:
                        combined_latest_stocks.append(stock)

    # Clean, normalize, and drop cross-file duplicates
    cleaned = []
    for stock in combined_latest_stocks:
        s = str(stock).upper().replace("NSE:", "").replace(".NS", "").strip()
        if 2 <= len(s) <= 20:
            cleaned.append(s)

    return sorted(list(set(cleaned)))

# =========================================================
# UTILS & BETTER SENTIMENT
# =========================================================
def generate_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

BULLISH = ["surge", "profit", "buy", "growth", "gain", "strong", "bullish", "record", "jumps", "rally", "up"]
BEARISH = ["fall", "loss", "weak", "sell", "drop", "bearish", "decline", "down", "crash"]

def sentiment(title):
    t = title.lower()
    
    # Simple boundaries to stop false positives (e.g., matching "start up" as "up")
    bull = sum(1 for w in BULLISH if re.search(r'\b' + w + r'\b', t))
    bear = sum(1 for w in BEARISH if re.search(r'\b' + w + r'\b', t))

    if bull > bear:
        return "🟢 Bullish"
    elif bear > bull:
        return "🔴 Bearish"
    return "⚪ Neutral"

# =========================================================
# GOOGLE NEWS RSS (OPTIMIZED SINGLE QUERY)
# =========================================================
def google_news(stock):
    results = []
    
    # Combining target constraints reduces network pressure from 4 calls to 1
    query = f'"{stock}" (share OR stock OR NSE OR market)'
    encoded_query = quote_plus(query)
    rss = f"https://news.google.com/rss/search?q={encoded_query}"

    try:
        feed = feedparser.parse(rss)
        print(f"QUERY FOR: {stock} | ENTRIES FOUND: {len(feed.entries)}")

        if not feed.entries:
            return results

        # Process top 10 news items
        for entry in feed.entries[:10]:
            # Google appends " - Publisher Name" at the end of titles.
            # Splitting clean helps prevent cross-publisher duplication checks.
            raw_title = entry.title
            clean_title = raw_title.split(" - ")[0].strip()

            results.append({
                "source": getattr(entry, "source", {}).get("text", "Google News"),
                "title": clean_title,
                "url": entry.link,
                "time": getattr(entry, "published", "")
            })
            
    except Exception as e:
        print(f"GOOGLE ERROR for {stock}: {e}")

    return results

# =========================================================
# BUILD MESSAGE
# =========================================================
def build_message(stock, item):
    s = sentiment(item["title"])

    msg = (
        f"📈 <b>{stock}</b>\n\n"
        f"Sentiment: {s}\n"
        f"📰 <b>{item['title']}</b>\n"
        f"🏢 Source: {item['source']}\n"
        f"⏰ {item['time']}\n\n"
        f"🔗 <a href='{item['url']}'>Read Full Story</a>"
    )
    return msg

# =========================================================
# PROCESS STOCK (RATE CONTROLLED)
# =========================================================
async def process_stock(stock):
    async with SEMAPHORE:
        print("PROCESSING:", stock)
        news = google_news(stock)

        if not news:
            print("NO NEWS FOUND FOR:", stock)
            return

        latest_unique = None

        # Identify the first fresh headline we haven't flagged yet
        for item in news:
            h = generate_hash(stock + item["title"])

            if h not in SENT_NEWS:
                latest_unique = item
                SENT_NEWS[h] = {
                    "stock": stock,
                    "time": str(datetime.now())
                }
                break

        if not latest_unique:
            print(f"ALL NEWS DUPLICATE FOR: {stock}")
            return

        message = build_message(stock, latest_unique)

        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=False  # Shows beautiful link thumbnails in Telegram
            )
            print("SENT TELEGRAM ALERT:", stock)
            
            # Subtle sleep to keep Telegram API relaxed between messages
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"TELEGRAM ERROR for {stock}: {e}")

# =========================================================
# MAIN
# =========================================================
async def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN or MY_CHAT_ID environment variables are missing.")
        return

    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 STOCK NEWS BOT STARTED")
    except Exception as e:
        print(f"INITIAL TELEGRAM CONNECTION FAILED: {e}")
        return

    stocks = extract_latest_stocks()
    print("EXTRACTED STOCKS TO CHECK:", stocks)

    if not stocks:
        await bot.send_message(chat_id=CHAT_ID, text="❌ No new stocks found in history files.")
        return

    tasks = [process_stock(stock) for stock in stocks]
    await asyncio.gather(*tasks)

    save_sent_news()
    
    await bot.send_message(chat_id=CHAT_ID, text="✅ NEWS SCAN COMPLETE")

# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    asyncio.run(main())
