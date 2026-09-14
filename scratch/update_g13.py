import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import logging
from services.sheets_client import SheetsClient

SPREADSHEET_ID = "1t1n71PXIs1rSTPha6pf5ugwbZ0a5fq44m1K7xg1KXfE"

sheets = SheetsClient()
# Row 13 is Item 12. Column G is URL (col index 7)
verified_url = "https://n.news.naver.com/mnews/article/092/0002436584?sid=105"

print(f"Updating Cell G13 (Row 13, Col G) in Google Sheet with verified URL:\n{verified_url}")
ws = sheets.news_spreadsheet.worksheet("06_News_All")
ws.update_cell(13, 7, verified_url)
print("Update success for G13!")
