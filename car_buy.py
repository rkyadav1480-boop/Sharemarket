import os
import json  
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. GitHub Secrets se environment variables fetch karna aur clean karna
GCP_CREDS_STR = os.environ.get("GCP_CREDENTIALS")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("MY_CHAT_ID", "").strip()

# --- Sheet URL (Apna exact URL yahan dalein) ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit#gid=0"


def send_telegram_message(message):
    """Telegram pe message bhejne ka safe function"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ CRITICAL ERROR: BOT_TOKEN ya CHAT_ID env variables se nahi mil pa raha hai!")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("[+] Telegram pe message successfully bhej diya gaya!")
        else:
            print(f"[-] Telegram API Error (Status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"[-] Telegram request fail ho gayi: {e}")


def scan_stocks_and_notify():
    try:
        if not GCP_CREDS_STR:
            print("❌ ERROR: GCP_CREDENTIALS missing hain!")
            return

        # 2. Google Sheets Authentication
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_CREDS_STR)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_url(SHEET_URL)
        worksheet = spreadsheet.get_worksheet(0)
        
        # 'I' column (Stock List) se saare stocks nikalna
        all_stocks = worksheet.col_values(9)[1:]  # I column = 9th column
        
        print(f"[+] Total {len(all_stocks)} rows mili hain. Filtering & Processing...")

        telegram_report = "📊 *Latest Stock Signals Report*\n"
        telegram_report += "--------------------------------------\n"
        telegram_report += "`📈 Stock` | `💰 Avg` | `🚨 Signal`\n"
        telegram_report += "--------------------------------------\n"
        
        valid_stocks_processed = 0

        for stock in all_stocks:
            # Agar cell khali hai, None hai, ya sirf spaces hain toh bina crash kiye skip karo
            if not stock or str(stock).strip() == "" or "None" in str(stock):
                continue
                
            stock_clean = str(stock).strip()
            
            try:
                # B1 cell me stock push karein
                worksheet.update_acell("B1", stock_clean)
                
                # Google Sheet calculation time ka delay
                time.sleep(2.5)
                
                # G2 aur H2 se data nikalna (.get use karke)
                # gspread .get() ek list of list deta hai (e.g. [['value']])
                res_g2 = worksheet.get("G2")
                res_h2 = worksheet.get("H2")
                
                # Safe formatting agar cell empty return karein
                cumulative_avg = res_g2[0][0] if res_g2 and res_g2[0] else "N/A"
                signal = res_h2[0][0] if res_h2 and res_h2[0] else "No Signal"
                
                # Report me data append karna
                telegram_report += f"*{stock_clean}* | {cumulative_avg} | `{signal}`\n"
                print(f"[+] Processed: {stock_clean} -> Avg: {cumulative_avg}, Signal: {signal}")
                
                valid_stocks_processed += 1
                
            except Exception as row_error:
                # Agar kisi ek stock me error aaye toh poora bot crash na ho, agla stock check kare
                print(f"[-] Row Error ({stock_clean}) skip ho raha hai: {row_error}")
                continue
            
        telegram_report += "--------------------------------------\n"
        telegram_report += "✅ *Scanning Complete!*"
        
        # Sirf tabhi message bhejein agar sach mein koi stock process hua ho
        if valid_stocks_processed > 0:
            send_telegram_message(telegram_report)
        else:
            print("[-] Koi bhi valid stock data nahi mila scan karne ke liye.")

    except Exception as e:
        print(f"[-] System level main error aaya: {e}")
        # Final secure fallback alert
        send_telegram_message(f"❌ *Stock Bot System Error:* {str(e)}")


if __name__ == "__main__":
    scan_stocks_and_notify()
