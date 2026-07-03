import yfinance as yf
from datetime import datetime
import pandas as pd
import requests # For Telegram API
import os # For environment variables

def get_daily_data(symbol, period="2y"):
    """yfinance से raw daily OHLCV list of dicts nikalo (no pandas)"""
    ticker = yf.Ticker(symbol)
    try:
        hist = ticker.history(period=period)
        if hist.empty:
            return []
    except Exception as e:
        return []

    hist = hist.reset_index()
    data = []
    for _, row in hist.iterrows():
        if 'Date' not in row:
            continue
        data.append({
            'date': row['Date'].to_pydatetime(),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row['Volume'])
        })
    return data

def to_weekly(daily_data):
    """Daily candles को ISO week के हिसाब से weekly OHLCV में aggregate करो"""
    weeks = {}
    for row in daily_data:
        year, week, _ = row['date'].isocalendar()
        key = (year, week)
        if key not in weeks:
            weeks[key] = {
                'date': row['date'], 'open': row['open'],
                'high': row['high'], 'low': row['low'],
                'close': row['close'], 'volume': row['volume']
            }
        else:
            w = weeks[key]
            w['high'] = max(w['high'], row['high'])
            w['low'] = min(w['low'], row['low'])
            w['close'] = row['close']          # last close of week
            w['volume'] += row['volume']
            w['date'] = row['date']            # update to last date in week

    # sorted list return करो (chronological)
    return [weeks[k] for k in sorted(weeks.keys())]

def weekly_breakout_scan(symbol, lookback_weeks=20, vol_multiplier=1.5):
    daily = get_daily_data(symbol)
    if not daily:
        return None

    weekly = to_weekly(daily)

    if len(weekly) < lookback_weeks + 11:
        return None  # पर्याप्त डेटा नहीं

    latest = weekly[-1]

    # rolling high of previous N weeks (excluding current week)
    prev_weeks = weekly[-(lookback_weeks+1):-1]
    if not prev_weeks:
        return None
    rolling_high = max(w['high'] for w in prev_weeks)

    # avg volume of last 10 weeks (excluding current)
    vol_window = weekly[-11:-1]
    if not vol_window:
        return None
    avg_vol = sum(w['volume'] for w in vol_window) / len(vol_window)

    breakout = latest['close'] > rolling_high
    vol_confirm = latest['volume'] > vol_multiplier * avg_vol
    strong_close = latest['close'] > (latest['low'] + 0.66 * (latest['high'] - latest['low']))

    return {
        'symbol': symbol,
        'close': round(latest['close'], 2),
        'rolling_high': round(rolling_high, 2),
        'breakout': breakout,
        'vol_confirm': vol_confirm,
        'strong_close': strong_close,
        'signal': breakout and vol_confirm and strong_close
    }

def send_telegram_message(message, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors
        print("Telegram message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")

# --- Nifty 500 के लिए परिवर्तन शुरू ---
print("Nifty 500 सिंबल लाए जा रहे हैं...")
try:
    url = 'https://en.wikipedia.org/wiki/NIFTY_500'
    tables = pd.read_html(url, storage_options={'User-Agent': "Mozilla/5.0"}, match='Symbol', header=0)

    nifty500_df = None
    for table in tables:
        if 'Symbol' in table.columns and 'Company Name' in table.columns:
            nifty500_df = table
            break

    if nifty500_df is not None:
        symbols_list = nifty500_df['Symbol'].dropna().astype(str).tolist()
        symbols = [symbol + ".NS" for symbol in symbols_list if not symbol.startswith('^')]
        print(f"सफलतापूर्वक {len(symbols)} Nifty 500 सिंबल लाए गए।")
    else:
        print("Wikipedia पर NIFTY 500 तालिका नहीं मिली। डिफ़ॉल्ट सिंबल का उपयोग किया जा रहा है।")
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"] # मूल पर वापस आ रहा है
except Exception as e:
    print(f"Wikipedia से Nifty 500 सिंबल लाने में त्रुटि: {e}। डिफ़ॉल्ट सिंबल का उपयोग किया जा रहा है।")
    symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"] # मूल पर वापस आ रहा है
# --- Nifty 500 के लिए परिवर्तन समाप्त ---


print("Nifty 500 स्टॉक्स के लिए साप्ताहिक ब्रेकआउट स्कैन चलाया जा रहा है...")

breakout_signals = [] # सिग्नल True वाले स्टॉक्स को स्टोर करने के लिए सूची
data_fetch_errors = [] # yfinance data fetching errors को स्टोर करने के लिए सूची

for sym in symbols:
    result = weekly_breakout_scan(sym)
    if result is None:
        data_fetch_errors.append(sym)
        continue # Skip to next symbol

    if result['signal']:
        # print(f"BREAKOUT SIGNAL: {result}") # अगर आप सभी रिजल्ट देखना चाहते हैं तो इसे अनकमेंट करें
        breakout_signals.append(result)

# Construct the message for Telegram
telegram_message_parts = ["*Nifty 500 Weekly Breakout Scan Results*\n"]

if breakout_signals:
    telegram_message_parts.append("\n*--- ब्रेकआउट सिग्नल वाले स्टॉक्स ---*\n")
    for signal_data in breakout_signals:
        b_sym = signal_data['symbol']
        tv_symbol = b_sym.replace('.NS', '')
        tradingview_link = f"https://in.tradingview.com/chart/?symbol=NSE%3A{tv_symbol}"
        telegram_message_parts.append(f"- {b_sym}: [TradingView]({tradingview_link})\n  `Close: {signal_data['close']}, Rolling High: {signal_data['rolling_high']}`")
else:
    telegram_message_parts.append("इस स्कैन में कोई ब्रेकआउट सिग्नल नहीं मिला।")

if data_fetch_errors:
    telegram_message_parts.append("\n*--- डेटा नहीं मिल पाया वाले स्टॉक्स (छोड़ा गया) ---*\n")
    telegram_message_parts.append("निम्नलिखित स्टॉक्स के लिए ऐतिहासिक डेटा उपलब्ध नहीं था या उसे प्राप्त करने में त्रुटि हुई:\n")
    for err_sym in data_fetch_errors:
        telegram_message_parts.append(f"- {err_sym}")

final_telegram_message = "\n".join(telegram_message_parts)

# Get Telegram credentials from environment variables
bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('MY_CHAT_ID')

if bot_token and chat_id:
    send_telegram_message(final_telegram_message, bot_token, chat_id)
else:
    print("Telegram BOT_TOKEN या MY_CHAT_ID वातावरण चर में सेट नहीं हैं। Telegram संदेश नहीं भेजा गया।")
    print("\n--- Final Results (Printed to Console) ---")
    print(final_telegram_message) # Print to console if Telegram not configured
