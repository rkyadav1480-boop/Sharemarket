import os
import json  
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. GitHub Secrets se environment variables fetch karna aur .strip() lagana (Crucial Fix for 404)
GCP_CREDS_STR = os.environ.get("GCP_CREDENTIALS")

# .strip() lagane se hidden spaces ya newline (\n) remove ho jayenge
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("MY_CHAT_ID", "").strip()

# --- MODIFIED: Sheet Name ki jagah Sheet ka poora URL yahan dalein ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit#gid=0"


def send_telegram_message(message):
    """Telegram pe message bhejne ka function"""
    if not BOT_TOKEN or not CHAT_ID:
        print("[-] Error: BOT_TOKEN ya CHAT_ID missing hai!")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("[+] Telegram pe message successfully bhej diya gaya!")
        else:
            # Agar ab bhi error aaye, toh exact issue pata chal sake
            print(f"[-] Telegram error: Status Code {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[-] Telegram bhejte waqt error aaya: {e}")

def scan_stocks_and_notify():
    try:
        # 2. Google Sheets Authentication
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_CREDS_STR)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # URL se open kiya aur index 0 se first page (gid=0) select kiya
        spreadsheet = client.open_by_url(SHEET_URL)
        worksheet = spreadsheet.get_worksheet(0)
        
        # 'I' column (Stock List) se saare stocks nikalna
        all_stocks = worksheet.col_values(9)[1:]  # I column = 9th column
        
        telegram_report = "📊 *Latest Stock Signals Report*\n"
        telegram_report += "--------------------------------------\n"
        telegram_report += "`📈 Stock` | `💰 Avg` | `🚨 Signal`\n"
        telegram_report += "--------------------------------------\n"
        
        print(f"[+] Total {len(all_stocks)} stocks mile. Processing shuru ho rahi hai...")

        for stock in all_stocks:
            if not stock or not stock.strip():
                continue
                
            stock_clean = stock.strip()
            
            # B1 cell me stock push karein
            worksheet.update_acell("B1", stock_clean)
            
            # Google Sheet ko calculate karne ke liye 2.5 seconds ka break dena
            time.sleep(2.5)
            
            # Fix: .acell().value ki jagah .get() use kiya jo stable hai
            cumulative_avg = worksheet.get("G2")
            signal = worksheet.get("H2")
            
            # Report me stock ki details jodna
            telegram_report += f"*{stock_clean}* | {cumulative_avg} | `{signal}`\n"
            print(f"Processed: {stock_clean} -> {signal}")
            
        telegram_report += "--------------------------------------\n"
        telegram_report += "✅ *Scanning Complete!*"
        
        # Final report Telegram par bhej dena
        send_telegram_message(telegram_report)

    except Exception as e:
        error_msg = f"❌ *Stock Bot Error:* {str(e)}"
        # Agar error authentication ya sheet ka hai, toh telegram par alert chala jayega
        send_telegram_message(error_msg)
        print(f"[-] Error aaya: {e}")

if __name__ == "__main__":
    scan_stocks_and_notify()
