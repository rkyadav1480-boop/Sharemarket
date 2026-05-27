import requests
import csv
import io
import json
import os
from datetime import datetime

# =========================
# CONFIG
# =========================
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
CHAT_ID        = os.environ.get("CHAT_ID", "")
SPREADSHEET_ID = "V1nZRvMKQ5PrbLJ36aaTm9b8Pwp4xolXB2XebWwa9SisA"  # ✅ नई ID
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

print("Done")
# Sheet download ke baad
print(f"Sheet status: {response.status_code}")
print(f"First 200 chars: {response.text[:200]}")

# Stocks ke baad  
print(f"Total Bull Run stocks: {len(stocks)}")

# Telegram ke baad
print(f"Telegram response: {send.status_code}")
print(f"Telegram response body: {send.text}")
