import os
import requests
import yfinance as yf
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("MY_CHAT_ID")

BUY_ABOVE_LOW = 0.05
TARGET_PCT = 0.0615
SL_PCT = 0.02

RAW_SYMBOLS = [
    "BSE","ZEEL","RELIANCE","SBIN","ADANIENT","HDFCBANK","ADANIGREEN",
    "MCX","ICICIBANK","BAJFINANCE","APOLLOHOSP","TCS","INFY","IDEA",
    "AXISBANK","MTARTECH","NETWEB","WIPRO","HFCL","TATASTEEL",
    "ADANIPOWER","BHARTIARTL","SCI","BHEL","VEDL","NATIONALUM",
    "SHRIRAMFIN","HINDALCO","DATAPATTNS","BEL","ITC","ANGELONE",
    "CGPOWER","NHPC","SUZLON","SAIL","RECLTD","TRENT","NTPC",
    "COFORGE","TECHM","ASHOKLEY","NBCC","JIOFIN","RVNL","PNB",
    "KAYNES","ACMESOLAR","LUPIN","LAURUSLABS","HAL","JSWSTEEL",
    "ONGC","POWERGRID","DLF","GRSE","TATACOMM","BDL","HINDCOPPER",
    "UPL","BPCL","IOC","CIPLA","MARICO","PAYTM","MAZDOCK","CDSL",
    "GAIL","DIVISLAB","MAXHEALTH","SBILIFE","LICI","SIEMENS","OIL",
    "LODHA","JINDALSTEL","PRESTIGE","INOXWIND","EXIDEIND","TATAPOWER",
    "BIOCON","MAHABANK","ZYDUSLIFE","OLECTRA","HCC","DRREDDY",
    "THERMAX","SCHNEIDER","APARINDS","SOLARINDS","THANGAMAYL"
]

def telegram(msg):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )

def get_top20():
    rs = []
    for stock in RAW_SYMBOLS:
        try:
            df = yf.download(stock + ".NS", period="1y",
                             auto_adjust=True, progress=False)

            if len(df) < 220:
                continue

            close = float(df["Close"].values[-1])
            dma50 = float(df["Close"].tail(50).mean())
            dma200 = float(df["Close"].tail(200).mean())

            if close <= dma200:
                continue

            if dma50 <= dma200:
                continue

            close_6m = float(df["Close"].values[-126])
            ret6m = ((close / close_6m) - 1) * 100

            rs.append((stock, ret6m))

        except Exception:
            pass

    rs.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in rs[:20]]

def scan_stock(stock):
    try:
        df = yf.download(stock + ".NS",
                         period="3mo",
                         auto_adjust=True,
                         progress=False)

        if len(df) < 30:
            return None

        low25 = float(df["Low"].tail(25).min())
        close = float(df["Close"].values[-1])

        gtt = round(low25 * 1.05, 2)

        if close < gtt:
            return None

        return {
            "stock": stock,
            "close": round(close, 2),
            "gtt": gtt,
            "target": round(gtt * (1 + TARGET_PCT), 2),
            "sl": round(gtt * (1 - SL_PCT), 2)
        }

    except Exception:
        return None

def main():
    top20 = get_top20()

    signals = []
    for s in top20:
        sig = scan_stock(s)
        if sig:
            signals.append(sig)

    if not signals:
        telegram(
            f"📭 No GTT Signal\n"
            f"Date: {datetime.now().strftime('%d-%m-%Y')}\n"
            f"Top20 scanned: {len(top20)}"
        )
        return

    msg = "🚀 GTT BUY SIGNALS\n\n"

    for s in signals:
        msg += (
            f"{s['stock']}\n"
            f"Close: {s['close']}\n"
            f"GTT: {s['gtt']}\n"
            f"Target: {s['target']}\n"
            f"SL: {s['sl']}\n\n"
        )

    telegram(msg)

if __name__ == "__main__":
    main()
