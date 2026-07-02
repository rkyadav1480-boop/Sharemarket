import yfinance as yf
import time
import re
import pandas as pd
import requests
import os

def get_daily_data(symbol, period="2y"):
    """yfinance se raw daily OHLCV list of dicts nikalo"""
    ticker = yf.Ticker(symbol)
    try:
        hist = ticker.history(period=period)
        if hist.empty:
            return []
    except Exception:
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
    """Daily candles ko ISO week ke hisaab se weekly OHLCV mein aggregate karo"""
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
            w['close'] = row['close']
            w['volume'] += row['volume']
            w['date'] = row['date']

    return [weeks[k] for k in sorted(weeks.keys())]


def weekly_breakout_scan(symbol, lookback_weeks=20, vol_multiplier=1.5):
    daily = get_daily_data(symbol)
    if not daily:
        return None

    weekly = to_weekly(daily)
    if len(weekly) < lookback_weeks + 11:
        return None

    latest = weekly[-1]
    prev_weeks = weekly[-(lookback_weeks + 1):-1]
    if not prev_weeks:
        return None
    rolling_high = max(w['high'] for w in prev_weeks)

    vol_window = weekly[-11:-1]
    if not vol_window:
        return None
    avg_vol = sum(w['volume'] for w in vol_window) / len(vol_window)

    breakout = latest['close'] > rolling_high
    vol_confirm = latest['volume'] > vol_multiplier * avg_vol
    strong_close = latest['close'] > (latest['low'] + 0.66 * (latest['high'] - latest['low']))

    # margin % - kitne % se breakout hua (sirf jab breakout True ho tab meaningful)
    margin_pct = ((latest['close'] - rolling_high) / rolling_high) * 100 if rolling_high else 0

    return {
        'symbol': symbol,
        'close': round(latest['close'], 2),
        'rolling_high': round(rolling_high, 2),
        'margin_pct': round(margin_pct, 2),
        'breakout': breakout,
        'vol_confirm': vol_confirm,
        'strong_close': strong_close,
        'signal': breakout and vol_confirm and strong_close
    }


def escape_markdown(text):
    """Telegram legacy Markdown ke liye special chars escape karo"""
    escape_chars = r'_*`['
    return re.sub(r'([%s])' % re.escape(escape_chars), r'\\\1', text)


def send_telegram_message(message, bot_token, chat_id):
    """4096 char limit ke hisaab se message chunks mein bhejo"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    MAX_LEN = 4000  # safety margin

    chunks = []
    while len(message) > MAX_LEN:
        split_at = message.rfind('\n', 0, MAX_LEN)
        if split_at == -1:
            split_at = MAX_LEN
        chunks.append(message[:split_at])
        message = message[split_at:]
    chunks.append(message)

    for i, chunk in enumerate(chunks):
        payload = {
            'chat_id': chat_id,
            'text': chunk,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            print(f"Telegram chunk {i+1}/{len(chunks)} sent successfully.")
        except requests.exceptions.RequestException as e:
            # Markdown parse error aane par plain text retry karo
            print(f"Error sending chunk {i+1}: {e}. Retrying without Markdown...")
            payload['parse_mode'] = None
            try:
                response = requests.post(url, json=payload, timeout=15)
                response.raise_for_status()
                print(f"Chunk {i+1} sent as plain text.")
            except requests.exceptions.RequestException as e2:
                print(f"Chunk {i+1} failed completely: {e2}")
        time.sleep(0.5)  # Telegram rate limit se bachne ke liye


# --- Nifty 500 symbols fetch ---
print("Nifty 500 symbol laaye ja rahe hain...")
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
        print(f"Safaltapoorvak {len(symbols)} Nifty 500 symbol laaye gaye.")
    else:
        print("Wikipedia par NIFTY 500 table nahi mili. Default symbols use ho rahe hain.")
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
except Exception as e:
    print(f"Wikipedia se symbols laane mein error: {e}. Default symbols use ho rahe hain.")
    symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

print("Nifty 500 stocks ke liye weekly breakout scan chalaya ja raha hai...")

strict_signals = []      # breakout + vol_confirm + strong_close (sab True)
breakout_only = []       # breakout True hai, but vol_confirm ya strong_close fail
data_fetch_errors = []

for idx, sym in enumerate(symbols):
    result = weekly_breakout_scan(sym)
    if result is None:
        data_fetch_errors.append(sym)
    elif result['breakout']:
        # Debug print - console mein har breakout ka pura detail dikhega
        print(
            f"{sym}: close={result['close']} rolling_high={result['rolling_high']} "
            f"margin={result['margin_pct']}% vol_confirm={result['vol_confirm']} "
            f"strong_close={result['strong_close']} => signal={result['signal']}"
        )
        if result['signal']:
            strict_signals.append(result)
        else:
            breakout_only.append(result)

    # progress + rate-limit friendly delay
    if (idx + 1) % 25 == 0:
        print(f"{idx + 1}/{len(symbols)} stocks processed...")
    time.sleep(0.3)  # Yahoo Finance block hone se bachne ke liye

# breakout_only ko margin % ke hisaab se sort karo (best pehle)
breakout_only.sort(key=lambda x: x['margin_pct'], reverse=True)
strict_signals.sort(key=lambda x: x['margin_pct'], reverse=True)


def format_stock_line(signal_data, show_flags=False):
    b_sym = signal_data['symbol']
    tv_symbol = b_sym.replace('.NS', '')
    tradingview_link = f"https://in.tradingview.com/chart/?symbol=NSE%3A{tv_symbol}"
    safe_sym = escape_markdown(b_sym)
    line = (
        f"- {safe_sym}: [TradingView]({tradingview_link})\n"
        f"  `Close: {signal_data['close']} | High: {signal_data['rolling_high']} | Margin: +{signal_data['margin_pct']}%`"
    )
    if show_flags:
        vol_mark = "✅" if signal_data['vol_confirm'] else "❌"
        close_mark = "✅" if signal_data['strong_close'] else "❌"
        line += f"\n  `Vol Confirm: {vol_mark}  Strong Close: {close_mark}`"
    return line


# --- Telegram message banao ---
telegram_message_parts = ["*Nifty 500 Weekly Breakout Scan Results*"]

if strict_signals:
    telegram_message_parts.append(
        f"\n*✅ CONFIRMED SIGNALS ({len(strict_signals)})*\n_Breakout + Volume + Strong Close - sab confirm_\n"
    )
    for s in strict_signals:
        telegram_message_parts.append(format_stock_line(s))
else:
    telegram_message_parts.append("\n*✅ CONFIRMED SIGNALS*\nKoi fully confirmed signal nahi mila is scan mein.")

if breakout_only:
    telegram_message_parts.append(
        f"\n\n*⚠️ BREAKOUT ONLY - WEAK ({len(breakout_only)})*\n_Price breakout hua, lekin volume ya close weak - caution ke saath dekhein_\n"
    )
    for s in breakout_only:
        telegram_message_parts.append(format_stock_line(s, show_flags=True))

if data_fetch_errors:
    telegram_message_parts.append(
        f"\n\n*--- Data Fetch Errors ---*\n{len(data_fetch_errors)} stocks ke liye data nahi mila (skip kiya gaya)."
    )

final_telegram_message = "\n".join(telegram_message_parts)

bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('MY_CHAT_ID')

if bot_token and chat_id:
    send_telegram_message(final_telegram_message, bot_token, chat_id)
else:
    print("Telegram BOT_TOKEN ya MY_CHAT_ID environment variables mein set nahi hain.")
    print("\n--- Final Results (Console) ---")
    print(final_telegram_message)
