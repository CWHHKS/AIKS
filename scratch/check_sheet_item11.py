import os
import sys
import logging
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.sheets_client import SheetsClient
from services.url_resolver import resolve_exact_news_url, is_valid_deep_link
from services.audit_agent import GPTNewsAuditor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CheckItem11")

def check_item11():
    sheets = SheetsClient()
    if not sheets.is_connected() or not sheets.news_spreadsheet:
        print("Error: Could not connect to Google Sheets!")
        return

    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    all_values = ws.get_all_values()

    if len(all_values) < 12:
        print(f"Sheet has only {len(all_values)} rows. Row 12 (Item 11) does not exist yet!")
        return

    row12 = all_values[11]  # 0-indexed row 11 is row 12 in 1-based index (Header + 11 items)
    headers = all_values[0]
    
    print("\n--- Google Sheet Row 12 (Item #11) ---")
    row_dict = dict(zip(headers, row12))
    for k, v in row_dict.items():
        print(f"  {k}: {v}")

    title = row_dict.get("제목", "") or row_dict.get("Title", "")
    media = row_dict.get("출처 매체", "") or row_dict.get("Source Media", "")
    url = row_dict.get("출처 URL", "") or row_dict.get("Source URL", "")

    print("\n--- URL Inspection & Multi-Agent Verification ---")
    print(f"Current URL in Sheet: {url}")
    print(f"Title: {title}")
    print(f"Media: {media}")

    # 1. Test deep link validity
    valid = is_valid_deep_link(url, title=title, media=media)
    print(f"Direct Deep-Link Valid (HTTP 200 & Path Check)? {valid}")

    # 2. Run GPT Auditor explicitly
    auditor = GPTNewsAuditor()
    print("GPT Auditor Available?", auditor.is_available())
    
    # Resolve exact direct URL
    resolved_url = resolve_exact_news_url(title, media, url)
    print(f"Resolved Direct Target Site URL: {resolved_url}")

if __name__ == "__main__":
    check_item11()
