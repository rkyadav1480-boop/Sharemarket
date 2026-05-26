import os
import json  
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables
GCP_CREDS_STR = os.environ.get("GCP_CREDENTIALS")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("MY_CHAT_ID", "").strip()

SHEET_URL = "https://docs.google.com/spreadsheets/d/1dCdDsPnvpL2zOjNBo6UOg7wsnK4rHEvisqC0RS4EYcE/edit?gid=0#gid=0"

def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("[-] Telegram skip: Token ya Chat ID missing.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # 4096 limit se zyada ho toh split karo
    messages = []
    if len(message) > 4096:
        lines = message.split("\n")
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 4090:
                messages.append(chunk)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk:
            messages.append(chunk)
    else:
        messages = [message]

    for msg in messages:
        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                print("[+] Message sent!")
            else:
                print(f"[-] Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[-] Exception: {e}")
        time.sleep(0.5)


def scan_stocks_and_notify():
    try:
        if not GCP_CREDS_STR:
            print("[-] GCP_CREDENTIALS missing.")
            return

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_CREDS_STR)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        print("[+] Google Sheets connected...")
        spreadsheet = client.open_by_url(SHEET_URL)
        worksheet = spreadsheet.get_worksheet(0)

        all_stocks = worksheet.col_values(9)[1:]  # I column
        print(f"[+] Total {len(all_stocks)} stocks mile.")

        buy_stocks = []

        for stock in all_stocks:
            if not stock or str(stock).strip() == "":
                continue
            stock_clean = str(stock).strip()

            worksheet.update_acell("B1", stock_clean)
            time.sleep(2.5)

            res_g2 = worksheet.get("G2")
            res_h2 = worksheet.get("H2")

            cumulative_avg = res_g2[0][0] if res_g2 and res_g2[0] else "N/A"
            signal = res_h2[0][0] if res_h2 and res_h2[0] else "No Signal"

            print(f"[+] {stock_clean} -> Avg: {cumulative_avg}, Signal: {signal}")

            if "BUY" in signal.upper():
                buy_stocks.append({
                    "name": stock_clean,
                    "avg": cumulative_avg,
                    "signal": signal
                })

        # ══════════════════════════════════
        #        REPORT FORMATTING
        # ══════════════════════════════════
        from datetime import datetime
        now = datetime.now().strftime("%d %b %Y | %I:%M %p")

        report = ""
        report += "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        report += "┃  📈 <b>STOCK BUY ALERT</b> 📈     ┃\n"
        report += "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        report += f"🕐 <i>{now}</i>\n"
        report += "─────────────────────────────\n\n"

        if buy_stocks:
            for i, s in enumerate(buy_stocks, 1):
                report += f"🔰 <b>#{i} {s['name']}</b>\n"
                report += f"   💰 Avg Price  : <code>{s['avg']}</code>\n"
                report += f"   🚦 Signal     : <b>{s['signal']}</b>\n"
                report += "   ─────────────────────\n"

            report += "\n"
            report += "┌─────────────────────────┐\n"
            report += f"│  ✅ BUY Stocks  : <b>{len(buy_stocks)}</b>        │\n"
            report += f"│  🔍 Total Scanned: <b>{len([s for s in all_stocks if s.strip()])}</b>      │\n"
            report += "└─────────────────────────┘\n"
            report += "\n💡 <i>Invest wisely. DYOR always.</i>"

        else:
            report += "⚠️ <b>Aaj koi BUY signal nahi mila.</b>\n\n"
            report += f"🔍 Total Scanned: <b>{len([s for s in all_stocks if s.strip()])}</b> stocks\n"
            report += "💡 <i>Market monitor hota rahega...</i>"

        send_telegram_message(report)

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        send_telegram_message(f"⚠️ <b>Bot Error</b>\n<code>{str(e)[:200]}</code>")


if __name__ == "__main__":
    scan_stocks_and_notify()