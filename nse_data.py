import requests, os, json
from datetime import datetime, date

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
CHAT_ID      = os.environ.get("MY_CHAT_ID", "")   # ← MY_CHAT_ID secret
HISTORY_FILE = "nse_history.json"

# ══════════════════════════════════════════════════════════════════════════════
#  NSE HOLIDAYS 2025-2026
# ══════════════════════════════════════════════════════════════════════════════

NSE_HOLIDAYS = {
    "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31",
    "2025-04-10", "2025-04-14", "2025-04-18", "2025-05-01",
    "2025-08-15", "2025-08-27", "2025-10-02", "2025-10-20",
    "2025-10-21", "2025-11-05", "2025-12-25",
    "2026-01-26", "2026-03-20", "2026-04-02", "2026-04-06",
    "2026-04-14", "2026-05-01", "2026-08-15", "2026-10-02",
    "2026-11-14", "2026-12-25",
}

def is_market_open():
    today     = date.today()
    today_str = today.strftime("%Y-%m-%d")
    weekday   = today.weekday()
    if weekday == 5: return False, "Aaj Saturday — market band 🔴"
    if weekday == 6: return False, "Aaj Sunday — market band 🔴"
    if today_str in NSE_HOLIDAYS: return False, f"NSE Holiday ({today_str}) 🔴"
    return True, "Market open ✅"

# ══════════════════════════════════════════════════════════════════════════════
#  HISTORY
# ══════════════════════════════════════════════════════════════════════════════

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
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

def save_today_movers(big_movers):
    today_str     = date.today().strftime("%Y-%m-%d")
    history       = load_history()
    history       = clean_old_history(history)
    today_symbols = set()
    for sector, stocks in big_movers.items():
        for sym, ltp, chg in stocks:
            if chg >= 3.0:
                today_symbols.add(sym)
    history[today_str] = list(today_symbols)
    save_history(history)
    print(f"💾 History saved: {len(today_symbols)} gainers ({today_str})")
    return history

def find_common_stocks(today_symbols, history):
    today_str = date.today().strftime("%Y-%m-%d")
    freq = {}
    for date_str, symbols in history.items():
        if date_str == today_str: continue
        for sym in symbols:
            if sym in today_symbols:
                freq[sym] = freq.get(sym, 0) + 1
    return [{"no": i, "symbol": sym, "days": cnt, "tv_link": tv_url(sym)}
            for i, (sym, cnt) in enumerate(sorted(freq.items(), key=lambda x: -x[1]), 1)]

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def tv_url(symbol):
    return f"https://www.tradingview.com/chart/?symbol=NSE%3A{symbol}"

def send_telegram(text):
    url    = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        r = requests.post(url, data={
            "chat_id":                  CHAT_ID,   # ← CHAT_ID variable (MY_CHAT_ID secret se)
            "text":                     chunk,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True
        })
        if r.status_code == 200:
            print("✅ Telegram sent")
        else:
            print(f"❌ Telegram error: {r.text}")

# ══════════════════════════════════════════════════════════════════════════════
#  YAHOO FINANCE — Index constituents fetch
# ══════════════════════════════════════════════════════════════════════════════

# Yahoo Finance index symbols
INDICES = {
    "NIFTY 50":          "^NSEI",
    "NIFTY BANK":        "^NSEBANK",
    "NIFTY IT":          "^CNXIT",
    "NIFTY PHARMA":      "^CNXPHARMA",
    "NIFTY FMCG":        "^CNXFMCG",
    "NIFTY METAL":       "^CNXMETAL",
    "NIFTY MIDCAP 100":  "^CNXMIDCAP",
}

# Top stocks per index (NSE symbols)
INDEX_STOCKS = {
    "NIFTY 50": [
        "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN",
        "BHARTIARTL","ITC","KOTAKBANK","LT","AXISBANK","ASIANPAINT","MARUTI",
        "TITAN","BAJFINANCE","NESTLEIND","WIPRO","ULTRACEMCO","POWERGRID",
        "NTPC","TECHM","HCLTECH","SUNPHARMA","ONGC","TATAMOTORS","TATASTEEL",
        "JSWSTEEL","ADANIENT","ADANIPORTS","BAJAJFINSV","DIVISLAB","DRREDDY",
        "EICHERMOT","GRASIM","HEROMOTOCO","HINDALCO","INDUSINDBK","M&M","SBILIFE",
        "APOLLOHOSP","BAJAJ-AUTO","BPCL","BRITANNIA","CIPLA","COALINDIA",
        "HDFCLIFE","LTIM","TATACONSUM","UPL"
    ],
    "NIFTY BANK": [
        "HDFCBANK","ICICIBANK","SBIN","AXISBANK","KOTAKBANK","INDUSINDBK",
        "BANDHANBNK","IDFCFIRSTB","FEDERALBNK","AUBANK","PNB","BANKBARODA"
    ],
    "NIFTY IT": [
        "TCS","INFY","HCLTECH","WIPRO","TECHM","LTIM","MPHASIS",
        "COFORGE","PERSISTENT","LTTS"
    ],
    "NIFTY PHARMA": [
        "SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","APOLLOHOSP",
        "TORNTPHARM","ALKEM","BIOCON","LUPIN","AUROPHARMA"
    ],
    "NIFTY FMCG": [
        "HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR",
        "MARICO","GODREJCP","COLPAL","TATACONSUM","UBL"
    ],
    "NIFTY METAL": [
        "TATASTEEL","JSWSTEEL","HINDALCO","SAIL","VEDL",
        "COALINDIA","NMDC","MOIL","APLAPOLLO","JINDALSTEL"
    ],
    "NIFTY MIDCAP 100": [
        "MUTHOOTFIN","PIIND","VOLTAS","GODREJPROP","AUROPHARMA",
        "INDUSTOWER","OBEROIRLTY","PAGEIND","SYNGENE","ABFRL"
    ],
}

def fetch_yahoo(symbol):
    """Yahoo Finance se stock data fetch karo."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r    = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        ltp  = round(meta.get("regularMarketPrice", 0), 2)
        prev = meta.get("chartPreviousClose") or meta.get("previousClose", ltp)
        chg  = round(((ltp - prev) / prev) * 100, 2) if prev else 0
        return ltp, chg
    except:
        return None, None

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def fetch_and_send():
    open_status, reason = is_market_open()
    if not open_status:
        print(reason)
        send_telegram(f"📅 <b>NSE Market Update</b>\n{reason}\nAaj script nahi chalegi.")
        return

    now_str   = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    today_str = date.today().strftime("%d-%m-%Y")
    summary   = {}
    big_movers = {}

    print("📥 Yahoo Finance se data fetch ho raha hai...")

    for index_name, stocks_list in INDEX_STOCKS.items():
        total_chg        = 0
        count            = 0
        movers_in_sector = []

        for sym in stocks_list:
            ltp, chg = fetch_yahoo(sym)
            if ltp is None: continue
            total_chg += chg
            count     += 1
            if abs(chg) >= 3.0:
                movers_in_sector.append((sym, ltp, chg))

        if count > 0:
            avg_chg         = round(total_chg / count, 2)
            summary[index_name] = avg_chg
            if movers_in_sector:
                big_movers[index_name] = movers_in_sector
            print(f"✅ {index_name}: {count} stocks | Avg: {avg_chg:+.2f}% | 3%+ movers: {len(movers_in_sector)}")

    # ══════════════════════════════════════════════════════
    #  MESSAGE 1 — Index Summary + Big Movers
    # ══════════════════════════════════════════════════════

    msg1 = (
        f"📊 <b>NSE Market Update</b>\n"
        f"📅 {today_str} | 🕙 {now_str}\n\n"
        f"<b>━━ INDEX SUMMARY ━━</b>\n"
    )

    for idx_name, chg in summary.items():
        arrow = "🟢▲" if chg > 0 else "🔴▼"
        msg1 += f"{arrow} <b>{idx_name}</b>: {chg:+.2f}%\n"

    if big_movers:
        msg1 += f"\n<b>━━ BIG MOVERS (3%+) ━━</b>\n"
        for sector, stocks in big_movers.items():
            gainers = sorted([s for s in stocks if s[2] > 0], key=lambda x: -x[2])
            losers  = sorted([s for s in stocks if s[2] < 0], key=lambda x:  x[2])
            if gainers or losers:
                msg1 += f"\n📌 <b>{sector}</b>\n"
            if gainers:
                msg1 += "🟢 <b>Gainers:</b>\n"
                for sym, ltp, chg in gainers:
                    msg1 += (
                        f"  • <b>{sym}</b> | ₹{ltp} | <b>+{chg:.2f}%</b>\n"
                        f"    📈 <a href='{tv_url(sym)}'>TradingView</a>\n"
                    )
            if losers:
                msg1 += "🔴 <b>Losers:</b>\n"
                for sym, ltp, chg in losers:
                    msg1 += (
                        f"  • <b>{sym}</b> | ₹{ltp} | <b>{chg:.2f}%</b>\n"
                        f"    📉 <a href='{tv_url(sym)}'>TradingView</a>\n"
                    )
    else:
        msg1 += "\n📭 Aaj koi stock 3% se zyada nahi badla."

    send_telegram(msg1)

    # ══════════════════════════════════════════════════════
    #  HISTORY SAVE + MESSAGE 2 — Common Stocks
    # ══════════════════════════════════════════════════════

    if big_movers:
        updated_history = save_today_movers(big_movers)
        today_gainers   = set()
        for sector, stocks in big_movers.items():
            for sym, ltp, chg in stocks:
                if chg >= 3.0:
                    today_gainers.add(sym)

        common = find_common_stocks(today_gainers, updated_history)

        if common:
            msg2 = (
                f"🔁 <b>Repeat Performers</b>\n"
                f"<i>Pichhle 30 dinon mein bhi 3%+ the</i>\n\n"
            )
            for stock in common:
                msg2 += (
                    f"<b>{stock['no']}. {stock['symbol']}</b>"
                    f" — {stock['days']} din\n"
                    f"📊 <a href='{stock['tv_link']}'>TradingView</a>\n\n"
                )
            send_telegram(msg2)
        else:
            send_telegram(
                "🔁 <b>Repeat Performers</b>\n"
                "<i>Aaj ke stocks pichhle 30 dinon ke data mein common nahi hain.</i>"
            )


if __name__ == "__main__":
    fetch_and_send()

