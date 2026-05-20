import os
import re
import json
import time
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

CHECK_INTERVAL = 300

JSON_FILES = [
    "nse_history.json",
    "bull_history.json"
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
# LOAD DUPLICATE FILE
# =========================================================

if os.path.exists(SENT_FILE):

    with open(SENT_FILE, "r") as f:
        SENT_NEWS = json.load(f)

else:
    SENT_NEWS = {}

# =========================================================
# SAVE DUPLICATE FILE
# =========================================================

def save_sent_news():

    with open(SENT_FILE, "w") as f:
        json.dump(SENT_NEWS, f, indent=2)

# =========================================================
# DATE DETECTION
# =========================================================

DATE_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}",
    r"\d{2}-\d{2}-\d{4}",
    r"\d{2}/\d{2}/\d{4}"
]

def find_latest_date(data):

    dates = []

    def scan(obj):

        if isinstance(obj, dict):

            for v in obj.values():
                scan(v)

        elif isinstance(obj, list):

            for i in obj:
                scan(i)

        elif isinstance(obj, str):

            for pattern in DATE_PATTERNS:

                found = re.findall(pattern, obj)

                for d in found:

                    try:

                        if "-" in d and len(d.split("-")[0]) == 4:

                            dt = datetime.strptime(
                                d,
                                "%Y-%m-%d"
                            )

                        elif "/" in d:

                            dt = datetime.strptime(
                                d,
                                "%d/%m/%Y"
                            )

                        else:

                            dt = datetime.strptime(
                                d,
                                "%d-%m-%Y"
                            )

                        dates.append(dt)

                    except:
                        pass

    scan(data)

    if not dates:
        return None

    return max(dates)

# =========================================================
# STOCK EXTRACTION ONLY FROM LATEST DATE
# =========================================================

def extract_latest_stocks():

    latest_global_date = None
    all_data = []

    # ===== LOAD FILES =====

    for file_name in JSON_FILES:

        if not os.path.exists(file_name):
            continue

        with open(file_name, "r") as f:

            try:
                data = json.load(f)
            except:
                continue

        latest_date = find_latest_date(data)

        all_data.append((data, latest_date))

        if latest_date:

            if (
                latest_global_date is None or
                latest_date > latest_global_date
            ):
                latest_global_date = latest_date

    # ===== EXTRACT STOCKS =====

    stocks = set()

    if latest_global_date is None:
        return []

    latest_str = latest_global_date.strftime("%Y-%m-%d")

    def scan(obj):

        if isinstance(obj, dict):

            text = json.dumps(obj)

            if latest_str in text:

                for v in obj.values():

                    if isinstance(v, str):

                        stock = (
                            v.upper()
                            .replace("NSE:", "")
                            .replace(".NS", "")
                            .strip()
                        )

                        if 2 <= len(stock) <= 20:
                            stocks.add(stock)

            for v in obj.values():
                scan(v)

        elif isinstance(obj, list):

            for i in obj:
                scan(i)

    for data, _ in all_data:
        scan(data)

    return sorted(list(stocks))

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
    "up",
    "gain",
    "strong",
    "bullish",
    "record"
]

BEARISH = [
    "fall",
    "loss",
    "down",
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
# MONEYCONTROL
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
# ALL NEWS
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
# MESSAGE
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

    while True:

        try:

            stocks = extract_latest_stocks()

            print(
                f"\n[{datetime.now()}]"
            )

            print(
                "LATEST STOCKS:",
                stocks
            )

            tasks = []

            for stock in stocks:

                tasks.append(
                    process_stock(stock)
                )

            await asyncio.gather(*tasks)

            save_sent_news()

        except Exception as e:

            print("MAIN ERROR:", e)

        await asyncio.sleep(
            CHECK_INTERVAL
        )

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())