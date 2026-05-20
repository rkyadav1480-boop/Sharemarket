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
# GOOGLE NEWS INDIA STOCK SEARCH
# =========================================================

def google_news(stock):

    results = []

    try:

        query = (
            f"{stock} NSE share market india"
        )

        rss = (
            "https://news.google.com/rss/search?"
            f"q={query}"
        )

        feed = feedparser.parse(rss)

        print(
            "GOOGLE ENTRIES:",
            stock,
            len(feed.entries)
        )

        for entry in feed.entries[:1]:

            title = entry.title
            link = entry.link

            published = getattr(
                entry,
                "published",
                ""
            )

            # FILTER BAD NEWS

            lower_title = title.lower()

            skip_words = [
                "sports",
                "football",
                "movie",
                "actor",
                "festival",
                "politics"
            ]

            if any(
                w in lower_title
                for w in skip_words
            ):
                continue

            results.append({

                "source": "Google News",

                "title": title,

                "url": link,

                "time": published
            })

    except Exception as e:

        print(
            "GOOGLE ERROR:",
            stock,
            e
        )

    return results

# =========================================================
# GET NEWS
# =========================================================

def get_all_news(stock):

    return google_news(stock)

# =========================================================
# BUILD MESSAGE
# =========================================================

def build_message(stock, items):

    msg = (
        f"📈 <b>{stock}</b>\n\n"
    )

    for n in items:

        s = sentiment(
            n["title"]
        )

        msg += (

            f"{s}\n"

            f"📰 <b>{n['title']}</b>\n"

            f"🏢 {n['source']}\n"

            f"⏰ {n['time']}\n"

            f"{n['url']}\n\n"
        )

    return msg[:4000]

# =========================================================
# PROCESS STOCK
# =========================================================

async def process_stock(stock):

    print("PROCESSING:", stock)

    news = get_all_news(stock)

    if not news:

        print("NO NEWS:", stock)
        return

    # ===== ONLY LATEST NEWS =====

    latest = news[0]

    # ===== UNIQUE HASH =====

    h = generate_hash(
        stock + latest["title"]
    )

    # ===== DUPLICATE CHECK =====

    if h in SENT_NEWS:

        print(
            "DUPLICATE:",
            stock
        )

        return

    # ===== SAVE =====

    SENT_NEWS[h] = {
        "stock": stock,
        "time": str(datetime.now())
    }

    # ===== BUILD MESSAGE =====

    message = build_message(
        stock,
        [latest]
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
        ) =========================================================
# MAIN
# =========================================================

async def main():

    await bot.send_message(
        chat_id=CHAT_ID,
        text="🚀 STOCK NEWS BOT STARTED"
    )

    try:

        stocks = (
            extract_latest_stocks()
        )

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

        print("DONE")

    except Exception as e:

        print(
            "MAIN ERROR:",
            e
        )

        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"❌ ERROR:\n{e}"
        )

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())