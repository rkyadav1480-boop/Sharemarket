import os
import json
import requests
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yfinance as yf

# --- CONFIGURATION ---
LOW_PERIOD = 25
GTT_MULT = 0.97
JSON_FILE = "gtt_stocks.json"

# Telegram Settings
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Google Sheets Settings
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")
GSPREAD_CREDS_JSON = os.environ.get("GSPREAD_CREDENTIALS")

now = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing!")
        return
    url = f"https://api.telegram.com/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload)
        print(f"✉️ Telegram status: {res.status_code}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def get_sheet_stocks():
    if not SPREADSHEET_URL or not GSPREAD_CREDS_JSON:
        print("⚠️ Google Sheet credentials missing!")
        return []
    try:
        creds_dict = json.loads(GSPREAD_CREDS_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        col_values = sheet.col_values(1)  # Column A
        
        # Header skip aur khali rows filter karein
        stocks = [r.strip() for r in col_values if r.strip()]
        if stocks and (stocks[0].upper() == "STOCKS" or "SYMBOL" in stocks[0].upper()):
            stocks = stocks[1:]
        return stocks
    except Exception as e:
        print(f"❌ Error fetching from Google Sheet: {e}")
        return []

def to_yf_symbol(raw):
    raw = raw.strip().upper()
    if raw.startswith("NSE:"):
        return raw.replace("NSE:", "") + ".NS"
    elif raw.startswith("BOM:"):
        return raw.replace("BOM:", "") + ".BO"
    return raw + ".NS"

def get_25d_low_and_gtt(symbol):
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        tk = yf.Ticker(symbol, session=session)
        hist = tk.history(period="2mo", auto_adjust=True)
        
        if hist is None or hist.empty or len(hist) < LOW_PERIOD:
            print(f"⚠️ {symbol} ka data nahi mila ya rows kam hain.")
            return None, None
            
        lows = hist["Low"].dropna().tolist()[-LOW_PERIOD:]
        low_25 = round(min(lows), 2)
        gtt = round(low_25 * GTT_MULT, 2)
        return low_25, gtt
    except Exception as e:
        print(f"❌ {symbol} fetch karne mein error aayi: {str(e)}")
        return None, None

def get_cmp(symbol):
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        tk = yf.Ticker(symbol, session=session)
        hist = tk.history(period="1d")
        if not hist.empty:
            return round(hist["Close"].iloc[-1], 2)
    except:
        pass
    return None

def load_saved_stocks():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_json(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)

def main():
    saved = load_saved_stocks()
    
    try:
        sheet_stocks = get_sheet_stocks()
        print(f"📋 Sheet se mile stocks: {sheet_stocks}")
    except Exception as e:
        print(f"❌ Sheet read karne mein error aayi: {str(e)}")
        sheet_stocks = []
        
    newly_added = []
    
    # New Stocks Tracking From Sheet
    for raw_original in sheet_stocks:
        raw = raw_original.strip().upper()
        
        if raw not in saved:
            symbol = to_yf_symbol(raw)
            print(f"🔄 Processing stock from sheet: {raw} ({symbol})")
            
            low_25, gtt = get_25d_low_and_gtt(symbol)
            
            saved[raw] = {
                "symbol": symbol,
                "low_25": low_25 if low_25 else 0.0,
                "gtt_price": gtt if gtt else 0.0,
                "added_date": datetime.today().strftime("%Y-%m-%d"),
                "alerted": False,
                "active": True,
                "status": "Success" if low_25 else "YFinance_Failed"
            }
            newly_added.append(raw)

    # Price comparison aur Alert check
    alerts = []
    for raw, info in saved.items():
        cmp_price = get_cmp(info["symbol"])
        if cmp_price is None:
            continue
            
        gtt = info["gtt_price"]
        if gtt > 0 and cmp_price <= gtt:
            alerts.append({
                "name": raw,
                "cmp": cmp_price,
                "gtt": gtt,
                "low_25": info["low_25"]
            })

    save_json(saved)
    print(f"💾 JSON file updated successfully. Newly added: {newly_added}")

    # Telegram Notification System
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
