import requests
import csv
import io
import json
import os
from datetime import datetime
import pandas as pd
import yfinance as yf
import mplfinance as mpf
def calculate_rsi(close, period=14):

    delta = close.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))
# =========================
# CONFIG
# =========================
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
CHAT_ID        = os.environ.get("MY_CHAT_ID", "")
SPREADSHEET_ID = "1nZRvMKQ5PrbLJ36aaTm9b8Pwp4xolXB2XebWwa9SisA"  # ✅ नई ID
GID            = "1191767584"
JSON_FILE      = "bullrun_turnover_history.json"

# =========================
# GOOGLE SHEET CSV URL
# =========================
SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/"
    f"{SPREADSHEET_ID}/export?format=csv&gid={GID}"
)

# =========================
# DOWNLOAD SHEET
# =========================
print("Downloading sheet...")
response = requests.get(SHEET_URL)
if response.status_code != 200:
    print("Failed to download sheet")
    exit()

# =========================
# READ CSV
# =========================
csv_reader = csv.reader(io.StringIO(response.text))
stocks = []

for row in csv_reader:
    if not row:
        continue
    stock_name = row[0].strip()
    if stock_name == "":
        continue
    # ✅ Header rows skip करो
    if stock_name.upper() in ["STOCK NAME", "NSE CODE"]:
        continue
    # ✅ Date row skip करो (जैसे 5/27/2026)
    if "/" in stock_name:
        continue
    if stock_name not in stocks:
        stocks.append(stock_name)

print(f"Total Bull Run stocks found: {len(stocks)}")

# =========================
# DATE
# =========================
today = datetime.now().strftime("%d-%m-%Y")

# =========================
# LOAD OLD JSON
# =========================
if os.path.exists(JSON_FILE):
    try:
        with open(JSON_FILE, "r") as f:
            history = json.load(f)
    except:
        history = {}
else:
    history = {}

# =========================
# CREATE TODAY DATA
# =========================
history[today] = []

# =========================
# TELEGRAM MESSAGE
# =========================
message = (
    f"📈 <b>Aaj Ke Stocks In Bull Run (Turnover Top 250)</b>\n"
    f"📅 {today}\n\n"
)

# =========================
# PROCESS STOCKS
# =========================
if not stocks:
    message += "⚠️ Aaj koi stock Bull Run mein nahi hai."
else:
    for i, stock in enumerate(stocks, start=1):
        tradingview_link = (
            f"https://www.tradingview.com/chart/"
            f"?symbol=NSE:{stock}"
        )
        history[today].append({
            "no": i,
            "stock": stock,
            "tradingview": tradingview_link
        })
        message += (
            f"<b>{i}. {stock}</b>\n"
            f"📊 <a href='{tradingview_link}'>Open Chart</a>\n\n"
        )

# =========================
# SAVE JSON
# =========================
with open(JSON_FILE, "w") as f:
    json.dump(history, f, indent=4)
print("✅ JSON updated")

# =========================
# SEND TELEGRAM MESSAGE
# =========================
# Telegram 4096 char limit handle करो
MAX_LEN = 4096
messages_to_send = []
while len(message) > MAX_LEN:
    split_at = message.rfind("\n\n", 0, MAX_LEN)
    if split_at == -1:
        split_at = MAX_LEN
    messages_to_send.append(message[:split_at])
    message = message[split_at:].strip()
messages_to_send.append(message)

telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

for msg in messages_to_send:
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    send = requests.post(telegram_url, data=payload)
    if send.status_code == 200:
        print("✅ Telegram message sent successfully")
    else:
        print("❌ Telegram send failed")
        print(send.text)
# =========================
# WEEKLY CHARTS TO TELEGRAM
# =========================

# =========================
# WEEKLY CHARTS TO TELEGRAM
# =========================

photo_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

for stock in stocks:

    try:

        print(f"Creating chart for {stock}")

        symbol = f"{stock}.NS"

        df = yf.download(
            symbol,
            period="5y",
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            continue

        # Weekly candles
        df = df.resample("W").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum"
        }).dropna()

        df["DMA50"] = df["Close"].rolling(50).mean()
        df["DMA200"] = df["Close"].rolling(200).mean()
        df["RSI"] = calculate_rsi(df["Close"])

        chart_file = f"{stock}_weekly.png"

        addplots = [

            mpf.make_addplot(
                df["DMA50"]
            ),

            mpf.make_addplot(
                df["DMA200"]
            ),

            mpf.make_addplot(
                df["RSI"],
                panel=1,
                ylabel="RSI"
            )
        ]

        mpf.plot(
            df,
            type="candle",
            style="yahoo",
            volume=True,
            addplot=addplots,
            figsize=(12, 8),
            savefig=chart_file
        )

        tradingview_link = (
            f"https://www.tradingview.com/chart/"
            f"?symbol=NSE:{stock}"
        )

        caption = (
            f"📈 {stock}\n\n"
            f"Weekly Chart\n"
            f"50 DMA\n"
            f"200 DMA\n"
            f"RSI(14)\n\n"
            f"{tradingview_link}"
        )

        with open(chart_file, "rb") as img:

            requests.post(
                photo_url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption
                },
                files={
                    "photo": img
                }
            )

        if os.path.exists(chart_file):
            os.remove(chart_file)

    except Exception as e:

        print(
            f"Chart error for {stock}: {e}"
        )
print("Done")
# Sheet download ke baad
print(f"Sheet status: {response.status_code}")
print(f"First 200 chars: {response.text[:200]}")

# Stocks ke baad  
print(f"Total Bull Run stocks: {len(stocks)}")

# Telegram ke baad
print(f"Telegram response: {send.status_code}")
print(f"Telegram response body: {send.text}")
