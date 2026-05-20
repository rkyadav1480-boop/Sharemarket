import os
import json
import hashlib
import asyncio
import feedparser
from urllib.parse import quote_plus
from datetime import datetime
from telegram import Bot

# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("MY_CHAT_ID")
JSON_FILES = ["nse_history.json", "bullrun_history.json"]
SENT_FILE = "sent_news.json"

# Concurrency control to avoid Telegram 429 Rate Limits
MAX_CONCURRENT_STOCKS = 3 
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_STOCKS)

bot = Bot(token=BOT_TOKEN)

# =========================================================
# LOAD / SAVE SENT NEWS
# =========================================================
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        try:
            SENT_NEWS = json.load(f)
        except json.JSONDecodeError:
            SENT_NEWS = {}
else:
    SENT_NEWS = {}

def save_sent_news():
    with open(SENT_FILE, "w") as f:
        json.dump(SENT_NEWS, f, indent=2)

# =========================================================
# EXTRACT LATEST STOCKS
# =========================================================
def extract_latest_stocks():
    latest_date = None
    latest_stocks = []

    for file_name in JSON_FILES:
        if not os.path.exists(file_name):
            continue
        try:
            with open(file_name, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"JSON ERROR {file_name}: {e}")
            continue

        dates = []
        for key in data.keys():
            try:
                if "-" in key and len(key.split("-")[0]) == 4:
                    dt = datetime.strptime(key, "%Y-%m-%d")
                else:
                    dt = datetime.strptime(key, "%d-%m-%Y")
                dates.append((dt, key))
            except ValueError:
                pass

        if not dates:
            continue

        current_latest_dt, current_key = max(dates)

        if latest_date is None or current_latest_dt > latest_date:
            latest_date = current_latest_dt
            latest_stocks = []
            values = data[current_key]

            if isinstance(values, list) and len(values) > 0:
                if isinstance(values[0], str):
                    latest_stocks.extend(values)
                elif isinstance(values[0], dict):
                    for item in values:
                        stock = item.get("stock")
                        if stock:
                            latest_stocks.append(stock)

    cleaned = []
    for stock in latest_stocks:
        s = str(stock).upper().replace("NSE:", "").replace(".NS", "").strip()
        if 2 <= len(s) <= 20:
            cleaned.append(s)

    return sorted(list(set(cleaned)))

# =========================================================
# SENTIMENT & UTILS
# =========================================================
def generate_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

BULLISH = ["surge", "profit", "buy", "growth", "gain", "strong", "bullish", "record", "jumps", "rally", "up"]
BEARISH = ["fall", "loss", "weak", "sell", "drop", "bearish", "decline", "down", "crash"]

def sentiment(title):
    t = title.lower()
    bull = sum(1 for w in BULLISH if w in t)
    bear = sum(1 for w in BEARISH if w in t)
    
    if bull > bear: return "🟢 Bullish"
    if bear > bull: return "🔴 Bearish"
    return "⚪ Neutral"

# =========================================================
# GOOGLE NEWS RSS (Optimized Single Request)
# =========================================================
def google_news(stock):
    results = []
    # Combined search strings down to 1 precise query to prevent IP bans
    query = f'"{stock}" (share OR stock OR NSE OR market)'
    encoded_query = quote_plus(query)
    rss = f"https://news.google.com/rss/search?q={encoded_query}"

    try:
        feed = feedparser.parse(rss)
        if not feed.entries:
            return results

        for entry in feed.entries[:10]:
            results.append({
                "source": getattr(entry, "source", {}).get("text", "Google News"),
                "title": entry.title,
                "url": entry.link,
                "time": getattr(entry, "published", "")
            })
    except Exception as e:
        print(f"GOOGLE ERROR for {stock}: {e}")

    return results

def build_message(stock, item):
    s = sentiment(item["title"])
    return (
        f"📈 <b>{stock}</b>\n\n"
        f"Sentiment: {s}\n"
        f"📰 <b>{item['title']}</b>\n"
        f"🏢 Source: {item['source']}\n"
        f"⏰ {item['time']}\n\n"
        f"🔗 <a href='{item['url']}'>Read Article</a>"
    )

# =========================================================
# PROCESS STOCK (Throttled via Semaphore)
# =========================================================
async def process_stock(stock):
    async with SEMAPHORE:  # Keeps concurrent network hits tight and polite
        print("PROCESSING:", stock)
        news = google_news(stock)

        if not news:
            return

        latest_unique = None
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
            return

        message = build_message(stock, latest_unique)

        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=False  # Changed to False so you see rich link previews in TG
            )
            print("SENT NOTIFICATION:", stock)
            # Short breathing room space out consecutive Telegram blasts
            await asyncio.sleep(1) 
        except Exception as e:
            print(f"TELEGRAM ERROR for {stock}: {e}")

# =========================================================
# MAIN
# =========================================================
async def main():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 STOCK NEWS BOT STARTED")
    except Exception as e:
        print(f"Initial Telegram connection failed: {e}. Check your BOT_TOKEN and CHAT_ID.")
        return

    stocks = extract_latest_stocks()
    print("EXTRACTED STOCKS:", stocks)

    if not stocks:
        await bot.send_message(chat_id=CHAT_ID, text="❌ No stocks found in history files.")
        return

    tasks = [process_stock(stock) for stock in stocks]
    await asyncio.gather(*tasks)

    save_sent_news()
    await bot.send_message(chat_id=CHAT_ID, text="✅ NEWS SCAN COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())
