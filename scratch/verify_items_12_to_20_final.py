import os
import sys
import logging
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.sheets_client import SheetsClient
from services.url_resolver import is_valid_deep_link

def verify_12_to_20():
    sheets = SheetsClient()
    if not sheets.is_connected() or not sheets.news_spreadsheet:
        print("Error: Could not connect to Google Sheets!")
        return

    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    all_values = ws.get_all_values()
    headers = all_values[0]

    print("\n=======================================================")
    print("      06_News_All Items #12 to #20 Verification Report")
    print("=======================================================\n")

    for row_idx in range(13, min(22, len(all_values) + 1)):
        row = all_values[row_idx - 1]
        row_dict = dict(zip(headers, row))
        item_no = row_dict.get("No.", str(row_idx - 1))
        title = row_dict.get("제목", "") or row_dict.get("Title", "")
        media = row_dict.get("출처 매체", "") or row_dict.get("Source Media", "")
        url = row_dict.get("출처 URL", "") or row_dict.get("Source URL", "")
        valid = is_valid_deep_link(url, title=title, media=media)
        
        status = "[VERIFIED OK]" if valid else "[CHECK REQUIRED]"
        print(f"Item #{item_no} (Row {row_idx:02d}) {status}")
        print(f"  Title : {title[:60]}...")
        print(f"  Media : {media}")
        print(f"  URL   : {url}\n")

if __name__ == "__main__":
    verify_12_to_20()
