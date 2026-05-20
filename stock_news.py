import os
import json
import hashlib
import asyncio
import feedparser

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

bot = Bot(token=BOT_TOKEN)

# =========================================================
# LOAD SENT NEWS
# =========================================================

if os.path.exists(SENT_FILE):

    with open(SENT_FILE, "r") as f:
        SENT_NEWS = json.load(f)

else:

    SENT_NEWS = {}

# =========================================================
# SAVE SENT NEWS
# =========================================================

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

            print("JSON ERROR:", file_name, e)
            continue

        dates = []

        for key in data.keys():

            try:

                # yyyy-mm-dd
                if "-" in key and len(key.split("-")[0]) == 4:

                    dt = datetime.strptime(
                        key,
                        "%Y-%m-%d"
                    )

                # dd-mm-yyyy
                else:

                    dt = datetime.strptime(
                        key,
                        "%d-%m-%Y"
                    )

                dates.append((dt, key))

            except:
                pass

        if not dates:
            continue

        current_latest_dt, current_key = max(dates)

        if (
            latest_date is None or
            current_latest_dt > latest_date
        ):

            latest_date = current_latest_dt

            latest_stocks = []

            values = data[current_key]

            # LIST OF STRINGS

            if (
                isinstance(values, list)
                and len(values) > 0
                and isinstance(values[0], str)
            ):

                latest_stocks.extend(values)

            # LIST OF DICTS

            elif (
                isinstance(values, list)
                and len(values) > 0
                and isinstance(values[0], dict)
            ):

                for item in values:

                    stock = item.get("stock")

                    if stock:
                        latest_stocks.append(stock)

    cleaned = []

    for stock in latest_stocks:

        s = (
            str(stock)
            .upper()
            .replace("NSE:", "")
            .replace(".NS", "")
            .strip()
        )

        if 2 <= len(s) <= 20:
            cleaned.append(s)

    return sorted(list(set(cleaned)))

# =========================================================
# HASH
# =========================================================

def generate_hash(text):

    return hashlib.md5(
        text.encode()
    ).hexdigest()

# =========================================================
# SENTIMENT
# =========================================================

BULLISH = [
    "surge",
    "profit",
    "buy",
    "growth",
    "gain",
    "strong",
    "bullish",
    "record",
    "jumps",
    "rally",
    "up"
]

BEARISH = [
    "fall",
    "loss",
    "weak",
    "sell",
    "drop",
    "bearish",
    "decline",
    "down",
    "crash"
]

def sentiment(title):

    t = title.lower()

    bull = sum(
        1 for w in BULLISH if w in t
    )

    bear = sum(
        1 for w in BEARISH if w in t
    )

    if bull > bear:
        return "🟢 Bullish"

    elif bear > bull:
        return "🔴 Bearish"

    return "⚪ Neutral"

# =========================================================
# GOOGLE NEWS RSS
# =========================================================

def google_news(stock):

    results = []

    queries = [

        f"{stock} share",

        f"{stock} stock",

        f"{stock} NSE",

        f"{stock} market"
    ]

    for q in queries:

        try:

            rss = (
                "https://news.google.com/rss/search?"
                f"q={q}"
            )

            feed = feedparser.parse(rss)

            print(
                "QUERY:",
                q,
                "ENTRIES:",
                len(feed.entries)
            )

            if not feed.entries:
                continue

            # GET TOP 10 NEWS
            for entry in feed.entries[:10]:

                title = entry.title
                link = entry.link

                published = getattr(
                    entry,
                    "published",
                    ""
                )

                results.append({

                    "source": "Google News",

                    "title": title,

                    "url": link,

                    "time": published
                })

            # FIRST SUCCESS ONLY
            break

        except Exception as e:

            print(
                "GOOGLE ERROR:",
                stock,
                e
            )

    return results

# =========================================================
# BUILD MESSAGE
# =========================================================

def build_message(stock, item):

    s = sentiment(
        item["title"]
    )

    msg = (
        f"📈 <b>{stock}</b>\n\n"
        f"{s}\n"
        f"📰 <b>{item['title']}</b>\n"
        f"🏢 {item['source']}\n"
        f"⏰ {item['time']}\n"
        f"{item['url']}"
    )

    return msg

# =========================================================
# PROCESS STOCK
# =========================================================

async def process_stock(stock):

    print("PROCESSING:", stock)

    news = google_news(stock)

    if not news:

        print("NO NEWS:", stock)
        return

    latest_unique = None

    # CHECK TOP 10 NEWS
    for item in news:

        h = generate_hash(
            stock + item["title"]
        )

        # FIRST NON DUPLICATE
        if h not in SENT_NEWS:

            latest_unique = item

            SENT_NEWS[h] = {
                "stock": stock,
                "time": str(datetime.now())
            }

            break

    if not latest_unique:

        print(
            "ALL NEWS DUPLICATE:",
            stock
        )

        return

    message = build_message(
        stock,
        latest_unique
    )

    try:

        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        print("SENT:", stock)

    except Exception as e:

        print(
            "TG ERROR:",
            stock,
            e
        )

# =========================================================
# MAIN
# =========================================================

async def main():

    await bot.send_message(
        chat_id=CHAT_ID,
        text="🚀 STOCK NEWS BOT STARTED"
    )

    stocks = extract_latest_stocks()

    print(
        "EXTRACTED STOCKS:",
        stocks
    )

    if not stocks:

        await bot.send_message(
            chat_id=CHAT_ID,
            text="❌ No stocks found"
        )

        return

    tasks = []

    for stock in stocks:

        tasks.append(
            process_stock(stock)
        )

    await asyncio.gather(*tasks)

    save_sent_news()

    await bot.send_message(
        chat_id=CHAT_ID,
        text="✅ NEWS SCAN COMPLETE"
    )

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())