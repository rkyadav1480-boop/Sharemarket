
"""
GTT Alert Script - With JSON Persistence (Permanent Tracking)
- Sheet se stocks padhta hai → JSON mein save karta hai
- JSON se track karta hai (chahe sheet se hata diya jaye)
- Roz CMP check karta hai → GTT hit? → Telegram alert
- Stock once added => JSON se auto remove nahi hoga
"""

import os
import json
import gspread
import yfinance as yf
import requests
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

BOT_TOKEN      = os.environ["BOT_TOKEN"]
CHAT_ID        = os.environ["MY_CHAT_ID"]
GCP_CREDS_JSON = os.environ["GCP_CREDENTIALS"]
SPREADSHEET    = "GTT Tracker"
SHEET_NAME     = "Sheet7"
JSON_FILE      = "gtt_stocks.json"
GTT_MULT       = 1.05
LOW_PERIOD     = 25

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })
    return resp.ok

def to_yf_symbol(raw):
    raw = raw.strip().upper()
    if raw.startswith("NSE:"):
        return raw.replace("NSE:", "") + ".NS"
    elif raw.startswith("BOM:"):
        return raw.replace("BOM:", "") + ".BO"
    return raw + ".NS"

def load_json():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    return {}

def save_json(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_sheet_stocks():
    creds_dict = json.loads(GCP_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open(SPREADSHEET)
    ws = sh.worksheet(SHEET_NAME)
    rows = ws.get_all_values()

    stocks = []
    for row in rows[1:]:
        if row and row[0].strip():
            stocks.append(row[0].strip())
    return stocks

def get_25d_low_and_gtt(symbol):
    try:
        end = datetime.today()
        start = end - timedelta(days=60)
        tk = yf.Ticker(symbol)
        hist = tk.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True
        )

        if hist is None or len(hist) < LOW_PERIOD:
            return None, None

        lows = hist["Low"].dropna().tolist()[-LOW_PERIOD:]
        low_25 = round(min(lows), 2)
        gtt = round(low_25 * GTT_MULT, 2)
        return low_25, gtt
    except:
        return None, None

def get_cmp(symbol):
    try:
        tk = yf.Ticker(symbol)
        return round(float(tk.fast_info["last_price"]), 2)
    except:
        try:
            hist = tk.history(period="1d")
            return round(float(hist["Close"].iloc[-1]), 2)
        except:
            return None

def main():
    now = datetime.now().strftime("%d-%b-%Y %H:%M")

    saved = load_json()

    try:
        sheet_stocks = get_sheet_stocks()
    except:
        sheet_stocks = []

    # Permanent JSON tracking
    newly_added = []

    for raw in sheet_stocks:
        if raw not in saved:

            symbol = to_yf_symbol(raw)
            low_25, gtt = get_25d_low_and_gtt(symbol)

            if low_25 and gtt:
                saved[raw] = {
                    "symbol": symbol,
                    "low_25": low_25,
                    "gtt_price": gtt,
                    "added_date": datetime.today().strftime("%Y-%m-%d"),
                    "alerted": False,
                    "active": True
                }
                newly_added.append(raw)

    # Existing stocks NEVER removed from JSON

    for raw, info in saved.items():
        symbol = info["symbol"]

        low_25, gtt = get_25d_low_and_gtt(symbol)

        if low_25 and gtt:
            saved[raw]["low_25"] = low_25
            saved[raw]["gtt_price"] = gtt
            saved[raw]["alerted"] = False

    alerts = []

    for raw, info in saved.items():

        cmp_price = get_cmp(info["symbol"])

        if cmp_price is None:
            continue

        gtt = info["gtt_price"]

        if cmp_price >= gtt:
            alerts.append({
                "name": raw,
                "cmp": cmp_price,
                "gtt": gtt,
                "low_25": info["low_25"]
            })

    save_json(saved)

    if alerts:

        msg = f"🚨 <b>GTT BUY ALERT</b>\n📅 {now}\n"

        for a in alerts:
            msg += (
                f"\n\n📌 <b>{a['name']}</b>"
                f"\nCMP : ₹{a['cmp']}"
                f"\n25D Low : ₹{a['low_25']}"
                f"\nGTT : ₹{a['gtt']}"
            )

        send_telegram(msg)

    else:
        send_telegram(
            f"📊 GTT Scan Complete\n"
            f"Stocks tracked : {len(saved)}\n"
            f"GTT Hit today : 0"
        )

if __name__ == "__main__":
    main()
