import os
import sys
import logging
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.sheets_client import SheetsClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UpdateItem11")

def update_item11():
    sheets = SheetsClient()
    if not sheets.is_connected() or not sheets.news_spreadsheet:
        print("Error: Could not connect to Google Sheets!")
        return

    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    
    # Item 11 is row 12 in 1-based index (Header is row 1, Item 1 is row 2 ... Item 11 is row 12)
    # Column G (7th column) is "출처 URL"
    new_url = "https://techcrunch.com/2024/07/11/softbank-acquires-uk-ai-chipmaker-graphcore/"
    ws.update_cell(12, 7, new_url)
    print(f"[OK] Successfully updated Row 12 (Item #11) Column G in Sheet 06_News_All to:\n{new_url}")

if __name__ == "__main__":
    update_item11()
