import os
import json
import requests
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

# --- CONFIGURATION ---
LOW_PERIOD = 25
GTT_MULT = 1.05  # 25-day low ka 105% - GTT trigger price
JSON_FILE = "gtt_stocks.json"

# Telegram Settings
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Google Sheets Settings (GitHub Secrets se aayega)
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL", "https://docs.google.com/spreadsheets/d/1vwtYZZb5una04I7p8CrDIRUTBWl1moDjHfO9w2tpYxU/edit?gid=1258719905#gid=1258719905")

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
    """Google Sheet se stocks fetch karo (public CSV export)"""
    if not SPREADSHEET_URL:
        print("⚠️ Google Sheet URL missing in GitHub Secrets!")
        return []
    try:
        # Public sheet URL ko CSV export format mein badalna
        if "/edit" in SPREADSHEET_URL:
            csv_url = SPREADSHEET_URL.split("/edit")[0] + "/export?format=csv"
        else:
            csv_url = SPREADSHEET_URL
            
        # Direct Pandas se bina kisi login ke read karein
        df = pd.read_csv(csv_url)
        
        if df.empty:
            print("⚠️ Sheet khali dikh rahi hai.")
            return []
            
        # Pehla column uthayein aur khali rows hatayein
        col_values = df.iloc[:, 0].dropna().tolist()
        stocks = [str(r).strip() for r in col_values if str(r).strip()]
        return stocks
    except Exception as e:
        print(f"❌ Error fetching from Public Google Sheet: {e}")
        return []

def to_yf_symbol(raw):
    """Stock symbol ko YFinance format mein convert karo"""
    raw = raw.strip().upper()
    if raw.startswith("NSE:"):
        return raw.replace("NSE:", "") + ".NS"
    elif raw.startswith("BOM:"):
        return raw.replace("BOM:", "") + ".BO"
    return raw + ".NS"

def get_25d_low_and_gtt(symbol):
    """25-day ka low aur GTT price fetch karo"""
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
        gtt = round(low_25 * GTT_MULT, 2)  # 25-day low * 1.05
        return low_25, gtt
    except Exception as e:
        print(f"❌ {symbol} fetch karne mein error aayi: {str(e)}")
        return None, None

def get_cmp(symbol):
    """Current market price fetch karo"""
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
    """Saved JSON file se stocks load karo"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                data = json.load(f)
                print(f"📂 Loaded {len(data)} stocks from JSON")
                return data
        except Exception as e:
            print(f"⚠️ JSON load error: {e}")
            return {}
    print(f"📂 JSON file nahi mila, naya create hoga")
    return {}

def save_json(data):
    """JSON file ko save karo"""
    try:
        with open(JSON_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print(f"💾 JSON saved with {len(data)} stocks")
    except Exception as e:
        print(f"❌ JSON save error: {e}")

def main():
    print(f"🚀 Script started at {now}")
    
    # Load pehle se saved stocks
    saved = load_saved_stocks()
    
    # Sheet se fresh stocks fetch karo
    sheet_stocks = get_sheet_stocks()
    print(f"📋 Sheet se {len(sheet_stocks)} stocks mile: {sheet_stocks}")
    
    newly_added = []
    
    # === STEP 1: NEW STOCKS ADD KARO ===
    for raw_original in sheet_stocks:
        raw = raw_original.strip().upper()
        
        # Agar stock pehle se nahi hai to add karo
        if raw not in saved:
            symbol = to_yf_symbol(raw)
            print(f"\n✨ NEW STOCK: {raw} ({symbol})")
            
            low_25, gtt = get_25d_low_and_gtt(symbol)
            
            # Agar data mil gaya to save karo
            if low_25 and gtt:
                saved[raw] = {
                    "symbol": symbol,
                    "low_25": low_25,
                    "gtt_price": gtt,
                    "added_date": datetime.today().strftime("%Y-%m-%d"),
                    "alerted": False,
                    "active": True,
                    "status": "Active"
                }
                newly_added.append(raw)
                print(f"   ✅ Added: {raw} | 25D Low: ₹{low_25} | GTT: ₹{gtt}")
            else:
                # Agar data nahi mila to bhi entry save karo but inactive
                saved[raw] = {
                    "symbol": symbol,
                    "low_25": 0.0,
                    "gtt_price": 0.0,
                    "added_date": datetime.today().strftime("%Y-%m-%d"),
                    "alerted": False,
                    "active": False,
                    "status": "YFinance_Failed"
                }
                print(f"   ❌ Failed: {raw} | YFinance data nahi mila")
        else:
            print(f"ℹ️  Already tracked: {raw}")
    
    # === STEP 2: GTT ALERT CHECK KARO ===
    print(f"\n🔍 Checking GTT alerts...")
    alerts = []
    
    for raw, info in saved.items():
        if not info["active"]:
            continue
            
        symbol = info["symbol"]
        cmp_price = get_cmp(symbol)
        
        if cmp_price is None:
            print(f"   ⚠️  {raw}: CMP fetch nahi hua")
            continue
        
        gtt = info["gtt_price"]
        low_25 = info["low_25"]
        
        # Alert check: agar CMP GTT price se kam ya barabar ho
        if gtt > 0 and cmp_price <= gtt:
            alerts.append({
                "name": raw,
                "cmp": cmp_price,
                "gtt": gtt,
                "low_25": low_25
            })
            print(f"   🚨 ALERT: {raw} | CMP: ₹{cmp_price} <= GTT: ₹{gtt}")
        else:
            print(f"   ✓ {raw} | CMP: ₹{cmp_price} | GTT: ₹{gtt}")
    
    # === STEP 3: JSON SAVE KARO ===
    save_json(saved)
    
    # === STEP 4: TELEGRAM NOTIFICATION ===
    print(f"\n📤 Sending Telegram notification...")
    
    if alerts:
        msg = f"🚨 <b>GTT BUY ALERT</b>\n📅 {now}\n\n"
        msg += f"<b>⚠️ {len(alerts)} stocks GTT hit!</b>\n"
        
        for a in alerts:
            msg += (
                f"\n📌 <b>{a['name']}</b>"
                f"\n   CMP: ₹{a['cmp']}"
                f"\n   25D Low: ₹{a['low_25']}"
                f"\n   GTT: ₹{a['gtt']}"
                f"\n   → Set GTT order at ₹{a['gtt']}"
            )
        send_telegram(msg)
    else:
        msg = (
            f"📊 <b>GTT Scan Complete</b>\n"
            f"📅 {now}\n\n"
            f"📈 Total stocks tracked: {len(saved)}\n"
            f"✅ Active: {sum(1 for s in saved.values() if s['active'])}\n"
            f"❌ Failed: {sum(1 for s in saved.values() if not s['active'])}\n"
            f"🚨 GTT Hit today: 0\n"
            f"✨ Newly added: {len(newly_added)}"
        )
        if newly_added:
            msg += f"\n\n🆕 New: {', '.join(newly_added)}"
        send_telegram(msg)
    
    print(f"✅ Scan complete!\n")

if __name__ == "__main__":
    main()
