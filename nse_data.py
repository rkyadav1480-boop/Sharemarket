import requests
import os
import json
import csv
import io
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== CONFIG ====================
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
CHAT_ID      = os.environ.get("MY_CHAT_ID", "")
HISTORY_FILE = "nse_history.json"
MAX_WORKERS  = 30  # Ek sath 30 requests parallel chalengi (Super Fast Speed)

# ==================== HOLIDAYS FUNCTION ====================
def get_nse_holidays():
    """NSE API se holidays fetch karo — fallback mein hardcoded list"""
    try:
        url     = "https://www.nseindia.com/api/holiday-master?type=trading"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer":    "https://www.nseindia.com",
            "Accept":     "application/json",
        }
        s = requests.Session()
        s.headers.update(headers)
        s.get("https://www.nseindia.com", timeout=10)
        r    = s.get(url, timeout=10)
        data = r.json()

        holidays = set()
        # NSE response mein "CM" = Capital Market trading holidays
        for item in data.get("CM", []):
            date_str = item.get("tradingDate", "")
            if date_str:
                try:
                    dt = datetime.strptime(date_str, "%d-%b-%Y")
                    holidays.add(dt.strftime("%Y-%m-%d"))
                except:
                    pass
        if holidays:
            print(f"✅ NSE holidays fetched: {len(holidays)}")
            return holidays
    except Exception as e:
        print(f"⚠️ Holiday fetch failed: {e} — fallback use kar raha hoon")

    # Fallback updated for accurate 2026/2027 market calendar
    return {
        "2026-01-26", "2026-03-20", "2026-04-02", "2026-04-06", "2026-04-14",
        "2026-05-01", "2026-08-15", "2026-10-02", "2026-11-14", "2026-12-25",
        "2027-01-26", "2027-03-24", "2027-04-09", "2027-04-14", "2027-05-01"
    }

def is_market_open():
    today     = date.today()
    today_str = today.strftime("%Y-%m-%d")
    weekday   = today.weekday()
    if weekday == 5: return False, "Aaj Saturday — market band 🔴"
    if weekday == 6: return False, "Aaj Sunday — market band 🔴"
    holidays = get_nse_holidays()
    if today_str in holidays: return False, f"NSE Holiday ({today_str}) 🔴"
    return True, "Market open ✅"

# ==================== HISTORY TRACKING ====================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def clean_old_history(history):
    today = date.today()
    for k in [k for k in list(history.keys())
              if (today - datetime.strptime(k, "%Y-%m-%d").date()).days > 30]:
        del history[k]
    return history

def save_today_movers(movers):
    today_str = date.today().strftime("%Y-%m-%d")
    history   = load_history()
    history   = clean_old_history(history)
    history[today_str] = [sym for sym, _, chg in movers if chg >= 3.0]
    save_history(history)
    print(f"💾 History saved: {len(history[today_str])} gainers ({today_str})")
    return history

def find_common_stocks(today_symbols, history):
    today_str = date.today().strftime("%Y-%m-%d")
    freq = {}
    for date_str, symbols in history.items():
        if date_str == today_str: continue
        for sym in symbols:
            if sym in today_symbols:
                freq[sym] = freq.get(sym, 0) + 1
    return sorted(freq.items(), key=lambda x: -x[1])

# ==================== TELEGRAM & UTILS ====================
def tv_url(symbol):
    return f"https://www.tradingview.com/chart/?symbol=NSE%3A{symbol}"

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram Config missing! Logging first 500 chars instead:")
        print(text[:500])
        return
    url    = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        r = requests.post(url, data={
            "chat_id":                  CHAT_ID,
            "text":                     chunk,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True
        })
        if r.status_code == 200:
            print("✅ Telegram sent")
        else:
            print(f"❌ Telegram error: {r.text}")

def get_nifty500_symbols():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer":    "https://www.nseindia.com"
    }
    urls = [
        "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "https://nseindia.com/content/indices/ind_nifty500list.csv",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200 and len(r.content) > 500:
                reader  = csv.DictReader(io.StringIO(r.text))
                symbols = [row["Symbol"].strip() for row in reader if row.get("Symbol","").strip()]
                if len(symbols) > 100:
                    print(f"✅ NSE CSV mili: {len(symbols)} stocks")
                    return list(dict.fromkeys(symbols))
        except Exception as e:
            print(f"⚠️ NSE CSV error: {e}")

    # Global array fallback map
    global NIFTY500_FALLBACK
    symbols = list(dict.fromkeys(NIFTY500_FALLBACK))
    print(f"⚠️ Fallback list use kar raha hoon: {len(symbols)} stocks")
    return symbols

def fetch_yahoo(symbol):
    url     = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        r    = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        ltp  = round(meta.get("regularMarketPrice", 0), 2)
        prev = meta.get("chartPreviousClose") or meta.get("previousClose", ltp)
        chg  = round(((ltp - prev) / prev) * 100, 2) if prev else 0
        return symbol, ltp, chg
    except:
        return symbol, None, None

# ==================== MAIN LOGIC EXECUTION ====================
def fetch_and_send():
    open_status, reason = is_market_open()
    if not open_status:
        print(reason)
        send_telegram(f"📅 <b>NSE Market Update</b>\n{reason}")
        return

    now_str   = datetime.now().strftime("%I:%M %p")
    today_str = date.today().strftime("%d-%m-%Y")

    symbols = get_nifty500_symbols()
    print(f"📋 Total stocks to scan: {len(symbols)}")

    all_gainers = []
    all_losers  = []
    total_chg   = 0
    count       = 0

    print("🚀 Scanning stocks in parallel threads...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_yahoo, sym): sym for sym in symbols}
        
        for future in as_completed(futures):
            sym, ltp, chg = future.result()
            if ltp is None or chg is None: 
                continue
                
            total_chg += chg
            count     += 1
            if chg >= 3.0:
                all_gainers.append((sym, ltp, chg))
            elif chg <= -3.0:
                all_losers.append((sym, ltp, chg))

    avg_chg = round(total_chg / count, 2) if count > 0 else 0
    print(f"📊 Scanned: {count} | Gainers: {len(all_gainers)} | Losers: {len(all_losers)}")

    all_gainers.sort(key=lambda x: -x[2])
    all_losers.sort(key=lambda x: x[2])

    # ━━ MESSAGE 1: MARKET OVERVIEW & SUMMARY ━━
    arrow = "🟢▲" if avg_chg > 0 else "🔴▼"
    msg1  = (
        f"📊 <b>NIFTY 500 Market Update</b>\n"
        f"📅 {today_str} | 🕙 {now_str}\n\n"
        f"{arrow} <b>Average Change:</b> {avg_chg:+.2f}%\n"
        f"📈 Gainers 3%+: <b>{len(all_gainers)}</b>\n"
        f"📉 Losers 3%-: <b>{len(all_losers)}</b>\n"
        f"🔍 Total scanned: <b>{count}</b> stocks\n"
    )

    if all_gainers:
        msg1 += f"\n<b>━━ TOP GAINERS (3%+) ━━</b>\n"
        for sym, ltp, chg in all_gainers[:25]:  # Pehle message mein compact snapshot
            msg1 += (
                f"🟢 <b>{sym}</b> | ₹{ltp} | <b>+{chg:.2f}%</b>\n"
                f"   📈 <a href='{tv_url(sym)}'>TradingView</a>\n"
            )
        if len(all_gainers) > 25:
            msg1 += f"\n<i>...aur {len(all_gainers)-25} stocks (Poori list niche hai)</i>\n"

    if all_losers:
        msg1 += f"\n<b>━━ TOP LOSERS (3%-) ━━</b>\n"
        for sym, ltp, chg in all_losers[:10]:
            msg1 += (
                f"🔴 <b>{sym}</b> | ₹{ltp} | <b>{chg:.2f}%</b>\n"
                f"   📉 <a href='{tv_url(sym)}'>TradingView</a>\n"
            )

    if not all_gainers and not all_losers:
        msg1 += "\n📭 Aaj koi stock 3% se zyada nahi badla."

    send_telegram(msg1)

    # ━━ MESSAGE 2: TOTAL PERFORMERS LIST (COMPLETE) ━━
    if all_gainers:
        msg2 = f"🔥 <b>TODAY'S TOTAL PERFORMERS ({len(all_gainers)})</b>\n"
        msg2 += f"<i>Aaj ke saare 3%+ gainers ki complete master list:</i>\n\n"
        
        for i, (sym, ltp, chg) in enumerate(all_gainers, 1):
            msg2 += f"{i}. <b>{sym}</b> (+{chg:.2f}%) | <a href='{tv_url(sym)}'>TV</a>\n"
        
        send_telegram(msg2)

        # ━━ MESSAGE 3: REPEAT PERFORMERS ANALYTICS ━━
        updated_history = save_today_movers(all_gainers)
        today_symbols   = {sym for sym, _, chg in all_gainers}
        common          = find_common_stocks(today_symbols, updated_history)

        if common:
            msg3 = "🔁 <b>Repeat Performers (30 Days History)</b>\n"
            msg3 += "<i>Yeh stocks pichhle 30 dinon mein bhi 3%+ momentum mein the:</i>\n\n"
            for i, (sym, days) in enumerate(common, 1):
                msg3 += f"🔥 <b>{sym}</b> — <b>{days} din</b> badha hai | <a href='{tv_url(sym)}'>Chart</a>\n"
        else:
            msg3 = (
                "🔁 <b>Repeat Performers</b>\n\n"
                "<i>Nayi Entry! Aaj ke saare gainers pichhle 30 dinon ke data mein fresh hain (koi repeat nahi).</i>"
            )
        
        send_telegram(msg3)


# ==================== MASTER FALLBACK DATA ====================
NIFTY500_FALLBACK = [
    # NIFTY 50
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN",
    "BHARTIARTL","ITC","KOTAKBANK","LT","AXISBANK","ASIANPAINT","MARUTI",
    "TITAN","BAJFINANCE","NESTLEIND","WIPRO","ULTRACEMCO","POWERGRID",
    "NTPC","TECHM","HCLTECH","SUNPHARMA","ONGC","TATAMOTORS","TATASTEEL",
    "JSWSTEEL","ADANIENT","ADANIPORTS","BAJAJFINSV","DIVISLAB","DRREDDY",
    "EICHERMOT","GRASIM","HEROMOTOCO","HINDALCO","INDUSINDBK","M&M","SBILIFE",
    "APOLLOHOSP","BAJAJ-AUTO","BPCL","BRITANNIA","CIPLA","COALINDIA",
    "HDFCLIFE","LTIM","TATACONSUM","UPL",
    # NIFTY NEXT 50
    "ADANIGREEN","ADANITRANS","AMBUJACEM","AUROPHARMA","BAJAJHLDNG",
    "BANKBARODA","BEL","BERGEPAINT","BHEL","BIOCON","BOSCHLTD",
    "CANBK","CHOLAFIN","COLPAL","DABUR","DMART","GAIL","GODREJCP",
    "GODREJPROP","HAL","HAVELLS","HDFCAMC","ICICIGI",
    "INDHOTEL","INDUSTOWER","IRCTC","LICI","LUPIN","MARICO",
    "MOTHERSON","MUTHOOTFIN","NAUKRI","OBEROIRLTY","OFSS","PAGEIND",
    "PEL","PIDILITIND","PIIND","PNB","RECLTD","SBICARD","SHREECEM",
    "SIEMENS","SRF","TORNTPHARM","TRENT","TVSMOTOR","VBL","VEDL",
    # NIFTY MIDCAP 100
    "ABFRL","ALKEM","ASTRAL","AUBANK","BANDHANBNK",
    "BHARATFORG","COFORGE","CONCOR","CROMPTON","CUMMINSIND","CYIENT",
    "DEEPAKNTR","DIXON","DRLAL","ELGIEQUIP","EMAMILTD","ENDURANCE",
    "ESCORTS","FEDERALBNK","GLENMARK","GMRINFRA","GRINDWELL",
    "HGINFRA","IDFCFIRSTB","IIFL","INDUSTOWER","IPCA","JKCEMENT",
    "JSWENERGY","JUBLFOOD","KANSAINER","KPIT","KPRMILL","L&TFH",
    "LAURUSLABS","LALPATHLAB","LTTS","MANAPPURAM","MAXHEALTH",
    "METROPOLIS","MFSL","MINDA","MPHASIS","NATCOPHARM","NCC",
    "PERSISTENT","PFIZER","PNCINFRA","POLYCAB","RADICO","RAMCOCEM",
    "RBLBANK","RVNL","SCHAEFFLER","SOLARINDS","SUNTV","SUPREMEIND",
    "SYNGENE","TATACHEM","TATAELXSI","TATAINVEST","THERMAX",
    "TIINDIA","TIMKEN","TORNTPOWER","TTKPRESTIG","UNIONBANK","VOLTAS",
    "WHIRLPOOL","ZYDUSLIFE","ANGELONE","CAMS","KFINTECH",
    "MOFSL","NUVAMA","IRFC","HUDCO","NBCC","SJVN","NHPC",
    # NIFTY SMALLCAP 100
    "HFCL","RAILTEL","IREDA","NTPCGREEN","RPOWER","JPPOWER",
    "POWERMECH","KEC","KALPATPOWR","APAR","KEI","FINOLEX","RRKABEL",
    "INOXWIND","SUZLON","PRAJIND","WAAREEENER","GREENPANEL","CENTURYPLY",
    "PRINCEPIPE","APOLLOPIPE","TEXINFRA","BIKAJI","DEVYANI",
    "SAPPHIRE","WESTLIFE","BARBEQUE","EASEMYTRIP","RATEGAIN","IXIGO",
    "NAZARA","HAPPYMINDS","TANLA","ROUTE","LATENTVIEW","DATAMATICS",
    "MASTEK","ZENSAR","JKPAPER","TNPL","AIAENG","CAMPUS","RELAXO",
    "BATA","METROBRAND","MEDPLUS","VMART","SHOPERSTOP","SHALBY",
    "RAINBOW","KRSNAA","VIJAYA","MEDANTA","YATHARTH","RPSGVENT",
    "SOLARA","NEULANDLAB","MARKSANS","SUVENPHAR","NIITMTS","PGIL",
    "GEOJITFSL","EMKAY","JMFINANCIL","EDELWEISS","SUBROS",
    "FIEM","SANDHAR","CRAFTSMAN","MAHINDCIE","SUPRAJIT","SAMVARDHNA",
    "UNIPARTS","SOM","GLOBUSSPR","TILAKNAGAR","GMBREW","GPPL",
    "ESABINDIA","VOLTAMP","PENIND","AMBER","PFC"
]

if __name__ == "__main__":
    fetch_and_send()
