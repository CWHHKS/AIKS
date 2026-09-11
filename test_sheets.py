import os
from services.sheets_client import SheetsClient

print("Initializing SheetsClient...")
client = SheetsClient()

print(f"Spreadsheet ID: {client.spreadsheet_id}")
print(f"Key filepath: {client.key_filepath}")
print(f"Key file exists: {os.path.exists(client.key_filepath)}")

if client.is_connected():
    print("SUCCESS: Google Sheets connected successfully!")
    try:
        count = client.get_registered_vendor_count()
        print(f"Total registered vendors: {count}")
    except Exception as e:
        print(f"Error reading vendor count: {e}")
else:
    print("FAILED: Google Sheets connection failed.")
    # Try custom authorization to see the traceback
    import gspread
    from google.oauth2.service_account import Credentials
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(client.key_filepath, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(client.spreadsheet_id)
        print("Manual auth check succeeded (should not happen if client.is_connected is False)")
    except Exception as e:
        print("Manual auth failed with error:")
        print(f"Error Type: {type(e)}")
        print(f"Error Details: {str(e)}")
