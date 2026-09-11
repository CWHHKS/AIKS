import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
error_log_sheet_name = os.getenv("ERROR_LOG_SHEET_NAME", "03_Error_Log")

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
key_path = os.path.join(os.getcwd(), "service_account.json")

creds = Credentials.from_service_account_file(key_path, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(spreadsheet_id)

wks = sh.worksheet(error_log_sheet_name)
rows = wks.get_all_values()

print(f"Total rows in Error Log: {len(rows)}")
if len(rows) > 1:
    print("\nLast 5 Error Logs:")
    for r in rows[-5:]:
        print("  | ".join(r))
else:
    print("No errors logged yet.")
