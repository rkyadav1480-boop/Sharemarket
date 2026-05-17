import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime, timedelta
import os
import json

# ─── CONFIG ───────────────────────────────────────────────
creds_json = os.environ.get('GCP_CREDENTIALS')
creds_dict = json.loads(creds_json)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1SnDY6-HjBN_HEDyJVPaqbA_1da5hv4tELmPBBoN6fhU"
worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Top 250 stocks")

# ─── NSE DATA FETCH ───────────────────────────────────────
def fetch_bhavcopy_for_date(date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                with z.open(z.namelist()[0]) as f:
                    df = pd.read_csv(f)

                    sym_col    = 'TckrSymb' if 'TckrSymb' in df.columns else 'SYMBOL'
                    close_col  = 'ClsPric'  if 'ClsPric'  in df.columns else 'CLOSE'
                    series_col = 'SctySrs'  if 'SctySrs'  in df.columns else 'SERIES'

                    vol_col = 'TtlTradgVol'
                    for c in ['TtlTradgVol', 'TtlTrdQty', 'TotTrdQty', 'TOTTRDQTY']:
                        if c in df.columns:
                            vol_col = c
                            break

                    if series_col in df.columns:
                        df = df[df[series_col].astype(str).str.strip() == 'EQ']

                    df = df[~df[sym_col].astype(str).str.contains(
                        'BEES|ETF|GOLD|LIQUID|CASE|SILVER|LIQ',
                        case=False, na=False
                    )]

                    df_top = df.sort_values(by=vol_col, ascending=False).head(250)
                    return df_top[[sym_col, vol_col, close_col]].values.tolist()
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# ─── EXECUTION ────────────────────────────────────────────
date = datetime.now()
data_to_insert = None
fetched_date_str = ""

for i in range(5):
    test_date = date - timedelta(days=i)
    if test_date.weekday() >= 5:
        continue
    data_to_insert = fetch_bhavcopy_for_date(test_date)
    if data_to_insert:
        fetched_date_str = test_date.strftime('%d-%b-%Y')
        break

# ─── SHEET UPDATE ─────────────────────────────────────────
if data_to_insert:
    worksheet.batch_clear(['A2:C251'])
    worksheet.update('A2', data_to_insert)
    ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%d-%b %H:%M')
    status_msg = f"Data Date: {fetched_date_str} | Last Update: {ist_now} (IST)"
    worksheet.update('K2', [[status_msg]])
    print("✅ Sheet Updated Successfully!")
else:
    print("❌ No data fetched!")
    exit(1)