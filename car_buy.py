import os
import json  
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables fetch karna
GCP_CREDS_STR = os.environ.get("GCP_CREDENTIALS")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("MY_CHAT_ID", "").strip()

# !!! APNI SHEET KA REAL URL YAHAN PASTE KAREIN !!!
SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit#gid=0"


def send_telegram_message(message):
    """Telegram pe HTML formatting ke sath secure message bhejna"""
    if not BOT_TOKEN or not CHAT_ID:
        print("[-] Telegram Message Skip: Token ya Chat ID khali hai.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # HTML parse mode sabse safe hota hai Markdown ke badle crashing se bachne ke liye
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            print("[+] Telegram message sent successfully!")
        else:
            print(f"[-] Telegram API Error (Status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"[-] Request Fail: {e}")


def scan_stocks_and_notify():
    try:
        if not GCP_CREDS_STR:
            print("[-] Error: GCP_CREDENTIALS environment variable nahi mila.")
            return

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_CREDS_STR)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        print("[+] Google Sheets connected. URL open kiya ja raha hai...")
        spreadsheet = client.open_by_url(SHEET_URL)
        worksheet = spreadsheet.get_worksheet(0)
        
        all_stocks = worksheet.col_values(9)[1:]  # I column
        print(f"[+] Total {len(all_stocks)} stocks mile scan ke liye.")

        # Report formatting ab HTML tags use karegi taaki string corrupt na ho
        telegram_report = "📊 <b>Latest Stock Signals Report</b>\n"
        telegram_report += "--------------------------------------\n"
        telegram_report += "<b>📈 Stock</b> | <b>💰 Avg</b> | <b>🚨 Signal</b>\n"
        telegram_report += "--------------------------------------\n"
        
        valid_stocks = 0

        for stock in all_stocks:
            if not stock or str(stock).strip() == "":
                continue
            stock_clean = str(stock).strip()
            
            # Google Sheet update cell
            worksheet.update_acell("B1", stock_clean)
            time.sleep(2.5)  # Sheet formula calculation delay
            
            res_g2 = worksheet.get("G2")
            res_h2 = worksheet.get("H2")
            
            cumulative_avg = res_g2[0][0] if res_g2 and res_g2[0] else "N/A"
            signal = res_h2[0][0] if res_h2 and res_h2[0] else "No Signal"
            
            # HTML code strings jodna
            telegram_report += f"<b>{stock_clean}</b> | {cumulative_avg} | <code>{signal}</code>\n"
            print(f"[+] Processed: {stock_clean} -> Avg: {cumulative_avg}, Signal: {signal}")
            valid_stocks += 1
            
        telegram_report += "--------------------------------------\n✅ <b>Scanning Complete!</b>"
        
        if valid_stocks > 0:
            send_telegram_message(telegram_report)
        else:
            print("[-] Kisi valid stock ka data process nahi hua.")

    except Exception as e:
        print(f"❌ CRITICAL ERROR IN MAIN LOOP: {e}")
        # Plain text notification bina kisi strict markdown symbol ke jisse 404 block ho sake
        plain_error = f"System Error Notification: Data Parsing/Connection problem on server. Details: {str(e)}"
        send_telegram_message(plain_error)

if __name__ == "__main__":
    scan_stocks_and_notify()
