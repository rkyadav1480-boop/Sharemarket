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
MAX_WORKERS  = 30  # Parallel worker threads

# ==================== SECTOR MAP ====================
# Symbol → Sector mapping (Nifty 500 ke major stocks)
SECTOR_MAP = {
    # IT / Technology
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
    "LTIM": "IT", "MPHASIS": "IT", "COFORGE": "IT", "PERSISTENT": "IT",
    "OFSS": "IT", "KPIT": "IT", "HAPPYMINDS": "IT", "ZENSAR": "IT",
    "MASTEK": "IT", "CYIENT": "IT", "LATENTVIEW": "IT", "DATAMATICS": "IT",
    "NIITMTS": "IT", "ROUTE": "IT", "TANLA": "IT",

    # Banking & Finance
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
    "KOTAKBANK": "Banking", "AXISBANK": "Banking", "INDUSINDBK": "Banking",
    "BANKBARODA": "Banking", "PNB": "Banking", "CANBK": "Banking",
    "UNIONBANK": "Banking", "IDFCFIRSTB": "Banking", "FEDERALBNK": "Banking",
    "RBLBANK": "Banking", "AUBANK": "Banking", "BANDHANBNK": "Banking",

    # NBFC / Financial Services
    "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "CHOLAFIN": "NBFC",
    "MUTHOOTFIN": "NBFC", "MANAPPURAM": "NBFC", "L&TFH": "NBFC",
    "SBICARD": "NBFC", "HDFCAMC": "NBFC", "ICICIGI": "NBFC",
    "SBILIFE": "NBFC", "HDFCLIFE": "NBFC", "LICI": "NBFC",
    "MOFSL": "NBFC", "ANGELONE": "NBFC", "EDELWEISS": "NBFC",
    "EMKAY": "NBFC", "GEOJITFSL": "NBFC", "JMFINANCIL": "NBFC",
    "NUVAMA": "NBFC", "CAMS": "NBFC", "KFINTECH": "NBFC",
    "PEL": "NBFC", "IIFL": "NBFC",

    # Pharma / Healthcare
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "DIVISLAB": "Pharma", "LUPIN": "Pharma", "AUROPHARMA": "Pharma",
    "BIOCON": "Pharma", "GLENMARK": "Pharma", "TORNTPHARM": "Pharma",
    "ALKEM": "Pharma", "IPCA": "Pharma", "NATCOPHARM": "Pharma",
    "LAURUSLABS": "Pharma", "PFIZER": "Pharma", "SYNGENE": "Pharma",
    "SOLARA": "Pharma", "NEULANDLAB": "Pharma", "MARKSANS": "Pharma",
    "SUVENPHAR": "Pharma", "ZYDUSLIFE": "Pharma", "APOLLOHOSP": "Pharma",
    "MAXHEALTH": "Pharma", "FORTIS": "Pharma", "RAINBOW": "Pharma",
    "SHALBY": "Pharma", "MEDANTA": "Pharma", "KRSNAA": "Pharma",
    "DRLAL": "Pharma", "METROPOLIS": "Pharma", "LALPATHLAB": "Pharma",
    "VIJAYA": "Pharma",

    # Auto & Auto Ancillaries
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "M&M": "Auto",
    "BAJAJ-AUTO": "Auto", "HEROMOTOCO": "Auto", "EICHERMOT": "Auto",
    "TVSMOTOR": "Auto", "MOTHERSON": "Auto", "BOSCHLTD": "Auto",
    "BHARATFORG": "Auto", "ENDURANCE": "Auto", "MAHINDCIE": "Auto",
    "SUBROS": "Auto", "FIEM": "Auto", "SANDHAR": "Auto",
    "CRAFTSMAN": "Auto", "SUPRAJIT": "Auto", "UNIPARTS": "Auto",
    "ESCORTS": "Auto", "TIINDIA": "Auto", "SAMVARDHNA": "Auto",

    # Energy / Power
    "NTPC": "Energy", "POWERGRID": "Energy", "ONGC": "Energy",
    "BPCL": "Energy", "GAIL": "Energy", "COALINDIA": "Energy",
    "ADANIGREEN": "Energy", "ADANITRANS": "Energy", "JSWENERGY": "Energy",
    "TORNTPOWER": "Energy", "SJVN": "Energy", "NHPC": "Energy",
    "NTPCGREEN": "Energy", "IREDA": "Energy", "RPOWER": "Energy",
    "JPPOWER": "Energy", "INOXWIND": "Energy", "SUZLON": "Energy",
    "PRAJIND": "Energy", "WAAREEENER": "Energy", "APAR": "Energy",
    "KEC": "Energy", "KALPATPOWR": "Energy", "POWERMECH": "Energy",

    # Infrastructure / Construction
    "LT": "Infra", "ADANIPORTS": "Infra", "ADANIENT": "Infra",
    "AMBUJACEM": "Infra", "SHREECEM": "Infra", "ULTRACEMCO": "Infra",
    "GMRINFRA": "Infra", "CONCOR": "Infra", "IRCTC": "Infra",
    "IRFC": "Infra", "HUDCO": "Infra", "NBCC": "Infra",
    "RVNL": "Infra", "HGINFRA": "Infra", "PNCINFRA": "Infra",
    "NCC": "Infra", "TEXINFRA": "Infra", "GPPL": "Infra",
    "RAJESHEXPO": "Infra",

    # Metals & Mining
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
    "VEDL": "Metals", "SAIL": "Metals", "NATIONALUM": "Metals",
    "HINDZINC": "Metals", "NMDC": "Metals", "MOIL": "Metals",
    "WELCORP": "Metals",

    # FMCG / Consumer
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG",
    "GODREJCP": "FMCG", "COLPAL": "FMCG", "EMAMILTD": "FMCG",
    "TATACONSUM": "FMCG", "VBL": "FMCG", "RADICO": "FMCG",
    "TILAKNAGAR": "FMCG", "GMBREW": "FMCG", "SOM": "FMCG",
    "BIKAJI": "FMCG",

    # Chemicals / Specialty
    "PIDILITIND": "Chemicals", "DEEPAKNTR": "Chemicals", "SRF": "Chemicals",
    "PIIND": "Chemicals", "AAVAS": "Chemicals", "ATUL": "Chemicals",
    "TATACHEM": "Chemicals", "UPL": "Chemicals", "SOLARINDS": "Chemicals",

    # Telecom
    "BHARTIARTL": "Telecom", "INDUSTOWER": "Telecom", "TTML": "Telecom",
    "HFCL": "Telecom", "RAILTEL": "Telecom", "TEJASNET": "Telecom",

    # Capital Goods / Engineering
    "SIEMENS": "Cap Goods", "HAVELLS": "Cap Goods", "ABB": "Cap Goods",
    "CUMMINSIND": "Cap Goods", "THERMAX": "Cap Goods", "BEL": "Cap Goods",
    "HAL": "Cap Goods", "BHEL": "Cap Goods", "KEI": "Cap Goods",
    "FINOLEX": "Cap Goods", "RRKABEL": "Cap Goods", "FINCABLES": "Cap Goods",
    "POLYCAB": "Cap Goods", "AMBER": "Cap Goods", "DIXON": "Cap Goods",
    "CROMPTON": "Cap Goods", "VOLTAMP": "Cap Goods", "ESABINDIA": "Cap Goods",
    "GRINDWELL": "Cap Goods", "PENIND": "Cap Goods", "ELGIEQUIP": "Cap Goods",
    "AIAENG": "Cap Goods", "JYOTICNC": "Cap Goods", "ELECON": "Cap Goods",
    "TIMKEN": "Cap Goods", "SCHAEFFLER": "Cap Goods",

    # Realty
    "GODREJPROP": "Realty", "OBEROIRLTY": "Realty", "DLF": "Realty",
    "PRESTIGE": "Realty", "BRIGADE": "Realty",

    # Media & Entertainment
    "ZEEL": "Media", "SUNTV": "Media", "SAREGAMA": "Media",
    "NAZARA": "Media", "PVR": "Media",

    # Consumer Discretionary / Retail
    "TITAN": "Consumer", "ASIANPAINT": "Consumer", "BERGEPAINT": "Consumer",
    "KANSAINER": "Consumer", "RELAXO": "Consumer", "BATA": "Consumer",
    "METROBRAND": "Consumer", "CAMPUS": "Consumer", "PAGEIND": "Consumer",
    "TRENT": "Consumer", "DMART": "Consumer", "VMART": "Consumer",
    "SHOPERSTOP": "Consumer", "MEDPLUS": "Consumer",
    "TTKPRESTIG": "Consumer", "WHIRLPOOL": "Consumer",

    # Hospitality & Travel
    "INDHOTEL": "Hospitality", "DEVYANI": "Hospitality",
    "WESTLIFE": "Hospitality", "BARBEQUE": "Hospitality",
    "SAPPHIRE": "Hospitality", "JUBLFOOD": "Hospitality",
    "EASEMYTRIP": "Hospitality", "IXIGO": "Hospitality",
    "RATEGAIN": "Hospitality",

    # Paper & Wood
    "JKPAPER": "Paper", "TNPL": "Paper",
    "GREENPANEL": "Paper", "CENTURYPLY": "Paper",

    # Pipes & Building Materials
    "PRINCEPIPE": "Building Mat", "APOLLOPIPE": "Building Mat",
    "ASTRAL": "Building Mat", "SUPREMEIND": "Building Mat",

    # Diversified / Conglomerate
    "RELIANCE": "Diversified", "BAJAJHLDNG": "Diversified",
    "TATAINVEST": "Diversified", "MFSL": "Diversified",
    "GRASIM": "Diversified",

    # Steel & Industrial
    "PENIND": "Industrial", "PFC": "Industrial", "RECLTD": "Industrial",
    "NAUKRI": "Industrial",
}

def get_sector_performance(results):
    """
    results: list of (symbol, ltp, chg) tuples — sabse pehle fetch hone ke baad pass karo
    Returns: sorted list of (sector, avg_chg, count, gainers, losers)
    """
    sector_data = {}  # sector → {total_chg, count, gainers, losers}

    for sym, ltp, chg in results:
        if ltp is None or chg is None:
            continue
        sector = SECTOR_MAP.get(sym, "Others")
        if sector not in sector_data:
            sector_data[sector] = {"total": 0.0, "count": 0, "gainers": 0, "losers": 0}
        sector_data[sector]["total"]  += chg
        sector_data[sector]["count"]  += 1
        if chg > 0:
            sector_data[sector]["gainers"] += 1
        elif chg < 0:
            sector_data[sector]["losers"]  += 1

    result = []
    for sec, d in sector_data.items():
        avg = round(d["total"] / d["count"], 2) if d["count"] > 0 else 0
        result.append((sec, avg, d["count"], d["gainers"], d["losers"]))

    # Average change se sort (best to worst)
    result.sort(key=lambda x: -x[1])
    return result

def format_sector_message(sector_perf):
    """Sector performance ka Telegram-ready message banao"""
    lines = ["<b>━━ SECTOR PERFORMANCE ━━</b>\n"]
    for sec, avg, count, gainers, losers in sector_perf:
        if avg > 0.5:
            icon = "🟢"
        elif avg < -0.5:
            icon = "🔴"
        else:
            icon = "🟡"
        bar = "▲" if avg > 0 else "▼"
        lines.append(
            f"{icon} <b>{sec}</b>: {bar}{abs(avg):.2f}%  "
            f"<i>({count} stocks | ↑{gainers} ↓{losers})</i>"
        )
    return "\n".join(lines)

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

def make_strength_bar(days):
    if days >= 8:
        return "🟩🟩🟩🟩🟩"
    elif days >= 5:
        return "🟩🟩🟩🟩⬜"
    elif days >= 3:
        return "🟩🟩🟩⬜⬜"
    elif days >= 2:
        return "🟩🟩⬜⬜⬜"
    else:
        return "🟩⬜⬜⬜⬜"

# ==================== TELEGRAM & UTILS ====================
def tv_url(symbol):
    return f"https://www.tradingview.com/chart/?symbol=NSE%3A{symbol}"

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram Config missing!")
        print(text[:500])
        return

    chat_ids = [cid.strip() for cid in CHAT_ID.split(",") if cid.strip()]

    for cid in chat_ids:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={
            "chat_id":                  cid,
            "text":                     text,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True
        })
        if r.status_code == 200:
            print(f"✅ Sent to {cid}")
        else:
            print(f"❌ Error ({cid}): {r.text}")

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

    all_results = []   # (sym, ltp, chg) — saare stocks
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
            all_results.append((sym, ltp, chg))
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

    # ━━━━━ SECTOR PERFORMANCE CALCULATE KARO ━━━━━
    sector_perf = get_sector_performance(all_results)

    # ━━ MESSAGE 1A: MARKET OVERVIEW ━━
    arrow = "🟢▲" if avg_chg > 0 else "🔴▼"
    msg1  = (
        f"📊 <b>NIFTY 500 Market Update</b>\n"
        f"📅 {today_str} | 🕙 {now_str}\n\n"
        f"{arrow} <b>Average Change:</b> {avg_chg:+.2f}%\n"
        f"📈 Gainers 3%+: <b>{len(all_gainers)}</b>\n"
        f"📉 Losers 3%-: <b>{len(all_losers)}</b>\n"
        f"🔍 Total scanned: <b>{count}</b> stocks"
    )
    send_telegram(msg1)

    # ━━ MESSAGE 1B: SECTOR PERFORMANCE ━━
    # Telegram 4096 char limit — sectors ko chunks mein bhejo
    CHUNK_SIZE = 20
    for idx in range(0, len(sector_perf), CHUNK_SIZE):
        chunk = sector_perf[idx:idx + CHUNK_SIZE]
        lines = []
        if idx == 0:
            lines.append("🏭 <b>SECTOR PERFORMANCE</b>\n")
        for sec, avg, count_s, gainers, losers in chunk:
            if avg > 0.5:
                icon = "🟢"
            elif avg < -0.5:
                icon = "🔴"
            else:
                icon = "🟡"
            bar = "▲" if avg > 0 else "▼"
            lines.append(
                f"{icon} <b>{sec}</b>: {bar}{abs(avg):.2f}%  "
                f"<i>({count_s} stocks | ↑{gainers} ↓{losers})</i>"
            )
        send_telegram("\n".join(lines))

    # ━━ MESSAGE 2: TOTAL PERFORMERS LIST ━━
    if all_gainers:
        chunk_size = 30
        for idx in range(0, len(all_gainers), chunk_size):
            chunk = all_gainers[idx:idx+chunk_size]
            msg2  = f"🔥 <b>TODAY'S TOTAL PERFORMERS ({idx+1} to {min(idx+chunk_size, len(all_gainers))})</b>\n"
            msg2 += f"<i>Aaj ke 3%+ gainers ki complete master list:</i>\n\n"
            for i, (sym, ltp, chg) in enumerate(chunk, idx + 1):
                msg2 += f"{i}. <b>{sym}</b> (+{chg:.2f}%) | 📊 <a href='{tv_url(sym)}'>Chart</a>\n"
            send_telegram(msg2)

        # ━━ MESSAGE 3: REPEAT PERFORMERS ━━
        updated_history = save_today_movers(all_gainers)
        today_symbols   = {sym for sym, _, chg in all_gainers}
        common          = find_common_stocks(today_symbols, updated_history)

        if common:
            for idx in range(0, len(common), chunk_size):
                chunk = common[idx:idx+chunk_size]
                msg3  = f"🔁 <b>Repeat Performers (History Batch {idx//chunk_size + 1})</b>\n"
                msg3 += "<i>Pichhle 30 dinon ke high momentum repeaters:</i>\n\n"
                for i, (sym, days) in enumerate(chunk, idx + 1):
                    s_bar = make_strength_bar(days)
                    msg3 += (
                        f"<b>{i}. {sym}</b>\n"
                        f"⚡ Strength: {s_bar} (<b>{days} Din</b>)\n"
                        f"📊 <a href='{tv_url(sym)}'>TradingView Chart</a>\n\n"
                    )
                send_telegram(msg3)
        else:
            send_telegram(
                "🔁 <b>Repeat Performers</b>\n\n"
                "<i>Nayi Entry! Aaj ke saare gainers pichhle 30 dinon ke data mein fresh hain.</i>"
            )


# ==================== MASTER FALLBACK DATA ====================
NIFTY500_FALLBACK = [
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN",
    "BHARTIARTL","ITC","KOTAKBANK","LT","AXISBANK","ASIANPAINT","MARUTI",
    "TITAN","BAJFINANCE","NESTLEIND","WIPRO","ULTRACEMCO","POWERGRID",
    "NTPC","TECHM","HCLTECH","SUNPHARMA","ONGC","TATAMOTORS","TATASTEEL",
    "JSWSTEEL","ADANIENT","ADANIPORTS","BAJAJFINSV","DIVISLAB","DRREDDY",
    "EICHERMOT","GRASIM","HEROMOTOCO","HINDALCO","INDUSINDBK","M&M","SBILIFE",
    "APOLLOHOSP","BAJAJ-AUTO","BPCL","BRITANNIA","CIPLA","COALINDIA",
    "HDFCLIFE","LTIM","TATACONSUM","UPL","ADANIGREEN","ADANITRANS",
    "AMBUJACEM","AUROPHARMA","BAJAJHLDNG","BANKBARODA","BEL","BERGEPAINT",
    "BHEL","BIOCON","BOSCHLTD","CANBK","CHOLAFIN","COLPAL","DABUR","DMART",
    "GAIL","GODREJCP","GODREJPROP","HAL","HAVELLS","HDFCAMC","ICICIGI",
    "INDHOTEL","INDUSTOWER","IRCTC","LICI","LUPIN","MARICO",
    "MOTHERSON","MUTHOOTFIN","NAUKRI","OBEROIRLTY","OFSS","PAGEIND",
    "PEL","PIDILITIND","PIIND","PNB","RECLTD","SBICARD","SHREECEM",
    "SIEMENS","SRF","TORNTPHARM","TRENT","TVSMOTOR","VBL","VEDL",
    "ABFRL","ALKEM","ASTRAL","AUBANK","BANDHANBNK","BHARATFORG",
    "COFORGE","CONCOR","CROMPTON","CUMMINSIND","CYIENT","DEEPAKNTR",
    "DIXON","DRLAL","ELGIEQUIP","EMAMILTD","ENDURANCE","ESCORTS",
    "FEDERALBNK","GLENMARK","GMRINFRA","GRINDWELL","HGINFRA",
    "IDFCFIRSTB","IIFL","INDUSTOWER","IPCA","JKCEMENT","JSWENERGY",
    "JUBLFOOD","KANSAINER","KPIT","KPRMILL","L&TFH","LAURUSLABS",
    "LALPATHLAB","LTTS","MANAPPURAM","MAXHEALTH","METROPOLIS","MFSL",
    "MINDA","MPHASIS","NATCOPHARM","NCC","PERSISTENT","PFIZER",
    "PNCINFRA","POLYCAB","RADICO","RAMCOCEM","RBLBANK","RVNL",
    "SCHAEFFLER","SOLARINDS","SUNTV","SUPREMEIND","SYNGENE","TATACHEM",
    "TATAELXSI","TATAINVEST","THERMAX","TIINDIA","TIMKEN","TORNTPOWER",
    "TTKPRESTIG","UNIONBANK","VOLTAS","WHIRLPOOL","ZYDUSLIFE",
    "ANGELONE","CAMS","KFINTECH","MOFSL","NUVAMA","IRFC","HUDCO",
    "NBCC","SJVN","NHPC","HFCL","RAILTEL","IREDA","NTPCGREEN",
    "RPOWER","JPPOWER","POWERMECH","KEC","KALPATPOWR","APAR","KEI",
    "FINOLEX","RRKABEL","INOXWIND","SUZLON","PRAJIND","WAAREEENER",
    "GREENPANEL","CENTURYPLY","PRINCEPIPE","APOLLOPIPE","TEXINFRA",
    "BIKAJI","DEVYANI","SAPPHIRE","WESTLIFE","BARBEQUE","EASEMYTRIP",
    "RATEGAIN","IXIGO","NAZARA","HAPPYMINDS","TANLA","ROUTE",
    "LATENTVIEW","DATAMATICS","MASTEK","ZENSAR","JKPAPER","TNPL",
    "AIAENG","CAMPUS","RELAXO","BATA","METROBRAND","MEDPLUS","VMART",
    "SHOPERSTOP","SHALBY","RAINBOW","KRSNAA","VIJAYA","MEDANTA",
    "YATHARTH","RPSGVENT","SOLARA","NEULANDLAB","MARKSANS","SUVENPHAR",
    "NIITMTS","PGIL","GEOJITFSL","EMKAY","JMFINANCIL","EDELWEISS",
    "SUBROS","FIEM","SANDHAR","CRAFTSMAN","MAHINDCIE","SUPRAJIT",
    "SAMVARDHNA","UNIPARTS","SOM","GLOBUSSPR","TILAKNAGAR","GMBREW",
    "GPPL","ESABINDIA","VOLTAMP","PENIND","AMBER","PFC"
]

if __name__ == "__main__":
    fetch_and_send()
