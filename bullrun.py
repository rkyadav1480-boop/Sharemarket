import requests
import csv
import io
import json
import os
from datetime import datetime

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID   = os.environ.get("CHAT_ID", "")

SPREADSHEET_ID = "1SnDY6-HjBN_HEDyJVPaqbA_1da5hv4tELmPBBoN6fhU"
GID            = "1191767584"

JSON_FILE = "bullrun_history.json"  # Repo mein save hoga

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

    if stock_name.upper() == "STOCK NAME":
        continue

    if stock_name not in stocks:
        stocks.append(stock_name)

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
    f"📈 <b>Aaj Ke Stocks In Bull Run</b>\n"
    f"📅 {today}\n\n"
)

# =========================
# PROCESS STOCKS
# =========================

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
# SAVE JSON — sirf 4 PM ke baad
# =========================

current_hour = datetime.now().hour  # IST hour

if current_hour >= 16:  # 16 = 4 PM
    with open(JSON_FILE, "w") as f:
        json.dump(history, f, indent=4)
    print("✅ JSON updated (4 PM ke baad hai — save kiya)")
else:
    print("⏭ JSON save skip (abhi 4 PM se pehle hai — sirf message bheja)")

# =========================
# SEND TELEGRAM MESSAGE
# =========================

telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

payload = {
    "chat_id": CHAT_ID,
    "text": message,
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
