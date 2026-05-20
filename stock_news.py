import os
import json
import hashlib
import asyncio
import feedparser
import requests

from bs4 import BeautifulSoup
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/122 Safari/537.36"
    )
}

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

        # ===== GET ALL DATES =====

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

        # ===== GLOBAL LATEST =====

        if (
            latest_date is None or
            current_latest_dt > latest_date
        ):

            latest_date = current_latest_dt

            latest_stocks = []

            values = data[current_key]

            # ===== LIST OF STRINGS =====

            if (
                isinstance(values, list)
                and len(values) > 0
                and isinstance(values[0], str)
            ):

                latest_stocks.extend(values)

            # ===== LIST OF DICTS =====

            elif (
                isinstance(values, list)
                and len(values) > 0
                and isinstance(values[0], dict)
            ):

                for item in values:

                    stock = item.get("stock")

                    if stock:
                        latest_stocks.append(stock)

    # ===== CLEAN =====

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
    "record"
]

BEARISH = [
    "fall",
    "loss",
    "weak",
    "sell",
    "drop",
    "bearish",
    "decline"
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
# MONEYCONTROL NEWS
# =========================================================

def moneycontrol_news(stock):

    results = []

    try:

        url = (
            f"https://www.moneycontrol.com/news/tags/"
            f"{stock.lower()}.html"
        )

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        items = soup.find_all(
            "li",
            class_="clearfix"
        )

        for item in items[:5]:

            h2 = item.find("h2")

            if not h2:
                continue

            a = h2.find("a")

            title = h2.get_text(strip=True)

            link = ""

            if a:
                link = a.get("href")

            span = item.find("span")

            tm = ""

            if span:
                tm = span.get_text(strip=True)

            results.append({
                "source": "Moneycontrol",
                "title": title,
                "url": link,
                "time": tm
            })

    except Exception as e:

        print("MC ERROR:", stock, e)

    return results

# =========================================================
# GOOGLE NEWS
# =========================================================

def google_news(stock):

    results = []

    try:

        rss = (
            "https://news.google.com/rss/search?"
            f"q={stock}+share+stock"
        )

        feed = feedparser.parse(rss)

        for entry in feed.entries[:5]:

            results.append({

                "source": "Google",

                "title": entry.title,

                "url": entry.link,

                "time": getattr(
                    entry,
                    "published",
                    ""
                )
            })

    except Exception as e:

        print("GOOGLE ERROR:", stock, e)

    return results

# =========================================================
# GET ALL NEWS
# =========================================================

def get_all_news(stock):

    news = []

    news.extend(
        moneycontrol_news(stock)
    )

    news.extend(
        google_news(stock)
    )

    return news

# =========================================================
# BUILD MESSAGE
# =========================================================

def build_message(stock, items):

    msg = f"📈 <b>{stock}</b>\n\n"

    for n in items:

        s = sentiment(n["title"])

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
        return

    unique = []

    for n in news:

        h = generate_hash(
            stock + n["title"]
        )

        if h in SENT_NEWS:
            continue

        SENT_NEWS[h] = {
            "stock": stock,
            "time": str(datetime.now())
        }

        unique.append(n)

    if not unique:
        return

    message = build_message(
        stock,
        unique
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

        print("TG ERROR:", stock, e)

# =========================================================
# MAIN
# =========================================================

async def main():

    await bot.send_message(
        chat_id=CHAT_ID,
        text="BOT STARTED"
    )

    try:

        stocks = extract_latest_stocks()

        print(
            "EXTRACTED STOCKS:",
            stocks
        )

        tasks = []

        for stock in stocks:

            tasks.append(
                process_stock(stock)
            )

        await asyncio.gather(*tasks)

        save_sent_news()

        print("DONE")

    except Exception as e:

        print("MAIN ERROR:", e)

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())