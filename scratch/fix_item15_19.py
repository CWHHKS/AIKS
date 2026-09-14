import os
import sys
import logging
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.sheets_client import SheetsClient
from services.url_resolver import resolve_exact_news_url, is_valid_deep_link

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Fix15And19")

def fix_item15_and_19():
    sheets = SheetsClient()
    if not sheets.is_connected() or not sheets.news_spreadsheet:
        print("Error: Could not connect to Google Sheets!")
        return

    ws = sheets.news_spreadsheet.worksheet("06_News_All")

    # Item #15 (Row 16): Safe Superintelligence $1B funding
    # Original URL was galapagos.org/travel/ (wrong domain)
    title_15 = "Safe Superintelligence raises $1B funding Ilya Sutskever"
    media_15 = "TechCrunch"
    url_15 = resolve_exact_news_url(title_15, media_15)
    print("Resolved Item #15 URL:", url_15)
    if url_15 and "techcrunch.com" in url_15:
        ws.update_cell(16, 7, url_15)
        print("[OK] Row 16 (Item #15) updated to:", url_15)

    # Item #19 (Row 20): Anthropic releases Claude 3.7 Sonnet
    # Original URL was homepage anthropic.com/
    title_19 = "Claude 3.7 Sonnet hybrid reasoning model"
    media_19 = "Anthropic"
    url_19 = resolve_exact_news_url(title_19, media_19)
    print("Resolved Item #19 URL:", url_19)
    if url_19:
        ws.update_cell(20, 7, url_19)
        print("[OK] Row 20 (Item #19) updated to:", url_19)

if __name__ == "__main__":
    fix_item15_and_19()
