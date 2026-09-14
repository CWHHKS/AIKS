import os
import sys
import logging
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.sheets_client import SheetsClient

def update_item15_final():
    sheets = SheetsClient()
    if not sheets.is_connected() or not sheets.news_spreadsheet:
        print("Error: Could not connect to Google Sheets!")
        return

    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    
    # Row 16 is Item 15
    new_url = "https://www.etnews.com/20240325000212"
    ws.update_cell(16, 7, new_url)
    print(f"[OK] Successfully updated Row 16 (Item #15) Column G to:\n{new_url}")

if __name__ == "__main__":
    update_item15_final()
