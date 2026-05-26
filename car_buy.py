import os
import json
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. GitHub Secrets se environment variables fetch karna
GCP_CREDS_STR = os.environ.get("GCP_CREDENTIALS")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("MY_CHAT_ID")

SHEET_NAME = "My Stock Portfolio"  # Apni Google Sheet ka exact naam yahan likhein

def send_telegram_message(message):
    """Telegram pe message bhejne ka function"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"  # Isse text thoda design me dikhega
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("[+] Telegram pe message successfully bhej diya gaya!")
        else:
            print(f"[-] Telegram error: {response.text}")
    except Exception as e:
        print(f"[-] Telegram bhejte waqt error aaya: {e}")

def scan_stocks_and_notify():
    try:
        # 2. Google Sheets Authentication (JSON String se directly read karega)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_CREDS_STR)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        worksheet = client.open(SHEET_NAME).get_worksheet(0)
        
        # 'I' कॉलम (Stock List) se saare stocks ki list nikalna
        all_stocks = worksheet.col_values(9)[1:]  # [1:] se header row chhoot jayegi
        
        telegram_report = "📊 *Latest Stock Signals Report*\n"
        telegram_report += "--------------------------------------\n"
        telegram_report += "`📈 Stock` | `💰 Avg` | `🚨 Signal`\n"
        telegram_report += "--------------------------------------\n"
        
        print(f"[+] Total {len(all_stocks)} stocks mile. Processing shuru ho rahi hai...")

        for stock in all_stocks:
            if not stock.strip():
                continue
                
            # B1 cell me stock push karein
            worksheet.update_acell("B1", stock.strip())
            
            # Google Sheet ko calculate karne ke liye 2.5 seconds ka break dena
            time.sleep(2.5)
            
            # G2 aur H2 se value read karna
            cumulative_avg = worksheet.acell("G2").value
            signal = worksheet.acell("H2").value
            
            # Report me stock ki details jodna
            telegram_report += f"*{stock.strip()}* | {cumulative_avg} | `{signal}`\n"
            print(f"Processed: {stock.strip()} -> {signal}")
            
        telegram_report += "--------------------------------------\n"
        telegram_report += "✅ *Scanning Complete!*"
        
        # Saare stocks scan hone ke baad final report Telegram par bhej dena
        send_telegram_message(telegram_report)

    except Exception as e:
        error_msg = f"❌ *Stock Bot Error:* {str(e)}"
        send_telegram_message(error_msg)
        print(f"[-] Error aaya: {e}")

if __name__ == "__main__":
    scan_stocks_and_notify()

