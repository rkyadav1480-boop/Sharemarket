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

SPREADSHEET_ID = "1Huz2D_MOXeGw9MrlNxW2YDP2zD0Hml7HiqoGvY7ERTE"
GID            = "1447246038"  # Sheet2

JSON_FILE = "gapup_history.json"

DISCLAIMER = "⚠️ <i>Ise dopaher 3 baje ke baad hi dekhe</i>"

# =========================
# SHEET URL
# =========================

SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/"
    f"{SPREADSHEET_ID}/export?format=csv&gid={GID}"
)

# =========================
# DATE TIME
# =========================

now       = datetime.now()
today     = now.strftime("%d-%m-%Y")
time_str  = now.strftime("%I:%M %p")
day_name  = now.strftime("%A")

# =========================
# DOWNLOAD SHEET
# =========================

print("Downloading sheet...")

response = requests.get(SHEET_URL)

if response.status_code != 200:
    print("Failed to download sheet")
    exit()

# =========================
# READ CSV — A3 se niche
# =========================

csv_reader = csv.reader(io.StringIO(response.text))
all_rows   = list(csv_reader)

stocks = []

# Row index 2 = A3 (0-indexed)
for row in all_rows[2:]:
    if not row:
        continue
    cell = row[0].strip()
    if cell == "" or cell.upper() == "#N/A" or cell == "0":
        continue
    # Valid stock name hona chahiye
    if cell and cell not in stocks:
        stocks.append(cell)

print(f"Stocks found: {stocks}")

# =========================
# LOAD JSON HISTORY
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
# TELEGRAM MESSAGE
# =========================

if stocks:
    # ✅ Stocks mile
    message = (
        f"📈 <b>Gapup Successful Stocks</b>\n"
        f"📅 {today} | 🕒 {time_str}\n\n"
    )

    for i, stock in enumerate(stocks, start=1):
        tradingview_link = f"https://www.tradingview.com/chart/?symbol=NSE:{stock}"
        message += (
            f"<b>{i}. {stock}</b>\n"
            f"📊 <a href='{tradingview_link}'>Open Chart</a>\n\n"
        )

    message += f"\n{DISCLAIMER}"

    # JSON mein save karo
    history[today] = {
        "time": time_str,
        "day": day_name,
        "stocks": stocks
    }

    with open(JSON_FILE, "w") as f:
        json.dump(history, f, indent=4)
    print("✅ JSON saved")

else:
    # ❌ Koi stock nahi
    message = (
        f"📉 <b>No Gapup Successful Today</b>\n"
        f"📅 {today} | 🕒 {time_str}\n\n"
        f"{DISCLAIMER}"
    )
    print("No stocks found today")

# =========================
# SEND TELEGRAM
# =========================

telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

payload = {
    "chat_id":                  CHAT_ID,
    "text":                     message,
    "parse_mode":               "HTML",
    "disable_web_page_preview": True
}

send = requests.post(telegram_url, data=payload)

if send.status_code == 200:
    print("✅ Telegram message sent!")
else:
    print("❌ Telegram failed:", send.text)

print("Done")
