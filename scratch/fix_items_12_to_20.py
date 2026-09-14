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
logger = logging.getLogger("Fix12To20")

def process_items_12_to_20():
    sheets = SheetsClient()
    if not sheets.is_connected() or not sheets.news_spreadsheet:
        print("Error: Could not connect to Google Sheets!")
        return

    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    all_values = ws.get_all_values()
    headers = all_values[0]

    # Index 12 is Item 12 (Row 13), up to Item 20 (Row 21)
    target_rows = range(13, min(22, len(all_values) + 1))
    
    auditor = GPTNewsAuditor()
    results = []

    print(f"\n--- Processing {len(target_rows)} items (Row 13 to Row {target_rows[-1]}) ---")
    
    for row_idx in target_rows:
        row_values = all_values[row_idx - 1]
        row_dict = dict(zip(headers, row_values))

        item_no = row_dict.get("No.", str(row_idx - 1))
        title = row_dict.get("제목", "") or row_dict.get("Title", "")
        media = row_dict.get("출처 매체", "") or row_dict.get("Source Media", "")
        current_url = row_dict.get("출처 URL", "") or row_dict.get("Source URL", "")

        print(f"\n[Item #{item_no} (Row {row_idx})]")
        print(f"  Title: {title[:50]}...")
        print(f"  Media: {media}")
        print(f"  Current URL: {current_url}")

        is_valid = is_valid_deep_link(current_url, title=title, media=media)
        final_url = current_url

        if is_valid:
            print("  Status: Already Valid Direct Deep-Link")
        else:
            print("  Status: Invalid / Homepage / Search Link. Resolving exact direct URL...")
            resolved = resolve_exact_news_url(title, media, current_url)
            if resolved:
                final_url = resolved
                ws.update_cell(row_idx, 7, final_url)
                print(f"  Updated URL in Sheet Row {row_idx}: {final_url}")
            else:
                print(f"  Warning: Could not resolve direct link for Row {row_idx}")

        results.append({
            "item_no": item_no,
            "row_idx": row_idx,
            "title": title,
            "media": media,
            "original_url": current_url,
            "final_url": final_url,
            "was_valid": is_valid
        })

    print("\n--- Processing Summary ---")
    for r in results:
        status_str = "VALID" if r["was_valid"] else "FIXED"
        print(f"Item #{r['item_no']} (Row {r['row_idx']}) [{status_str}]: {r['final_url']}")

if __name__ == "__main__":
    process_items_12_to_20()
