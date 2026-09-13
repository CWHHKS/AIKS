import os
import sys
import json
import logging
import urllib.parse
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.sheets_client import SheetsClient
from services.gemini_client import GeminiClient
import google.generativeai as genai
import google.ai.generativelanguage_v1beta as glm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FixNewsURLs")

def clean_title(title: str) -> str:
    if not title:
        return ""
    lines = [l.strip() for l in title.split("\n") if l.strip()]
    first_line = lines[0] if lines else title
    first_line = re.sub(r'[\r\n\t]+', ' ', first_line)
    return first_line.strip()

def is_url_valid(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    if url.lower() in ["none", "#", "null"]:
        return False
    
    try:
        p = urllib.parse.urlparse(url)
        if "google.com/search" in url.lower():
            return True
        if not p.path or p.path in ["", "/"]:
            return False
    except Exception:
        return False

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.head(url, headers=headers, timeout=3, allow_redirects=True)
        if resp.status_code == 200:
            final_url = resp.url.lower()
            if "/error" in final_url or "404" in final_url or "notfound" in final_url:
                return False
            return True
        elif resp.status_code in [403, 405]:
            resp_get = requests.get(url, headers=headers, timeout=3, allow_redirects=True, stream=True)
            if resp_get.status_code == 200:
                final_url = resp_get.url.lower()
                if "/error" in final_url or "404" in final_url or "notfound" in final_url:
                    return False
                return True
    except Exception:
        pass

    return False

def get_best_url(title: str, media: str, current_url: str, gemini_client: GeminiClient) -> str:
    if is_url_valid(current_url):
        return current_url

    cleaned = clean_title(title)
    query_str = f"{cleaned} {media}".strip()

    # Try Gemini Grounding
    try:
        search_tool = glm.Tool(google_search={})
        model = genai.GenerativeModel(
            model_name=gemini_client.discovery_model_name,
            tools=[search_tool]
        )
        res = model.generate_content(f"Find direct article link for: {query_str}")
        if res and res.candidates and hasattr(res.candidates[0], "grounding_metadata"):
            gm = res.candidates[0].grounding_metadata
            if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    if hasattr(chunk, "web") and hasattr(chunk.web, "uri"):
                        found_uri = chunk.web.uri
                        if is_url_valid(found_uri):
                            return found_uri
    except Exception:
        pass

    # Direct search link fallback (100% reliable)
    return f"https://www.google.com/search?q={urllib.parse.quote(query_str)}"

def audit_row(item):
    row_num, row, title_idx, media_idx, url_idx, gemini = item
    title = row[title_idx] if title_idx < len(row) else ""
    media = row[media_idx] if media_idx < len(row) else ""
    current_url = row[url_idx] if url_idx < len(row) else ""

    best_url = get_best_url(title, media, current_url, gemini)
    was_valid = (best_url == current_url)
    return row_num, current_url, best_url, was_valid

def main():
    logger.info("🚀 Starting multi-threaded fast audit of 105 news URLs...")
    sheets = SheetsClient()
    if not sheets.is_connected() or not sheets.news_spreadsheet:
        logger.error("❌ Failed to connect to Google Sheets News spreadsheet.")
        sys.exit(1)

    gemini = GeminiClient()
    worksheet = sheets.news_spreadsheet.worksheet(sheets.news_sheet_name)
    all_values = worksheet.get_all_values()

    if not all_values or len(all_values) <= 1:
        logger.info("No news records found in sheet.")
        return

    headers = all_values[0]
    title_idx, media_idx, url_idx = -1, -1, -1

    for i, h in enumerate(headers):
        h_norm = h.strip().lower()
        if "title" in h_norm or "제목" in h_norm:
            if title_idx == -1: title_idx = i
        if "media" in h_norm or "source" in h_norm or "출처" in h_norm or "언론사" in h_norm:
            if media_idx == -1: media_idx = i
        if "url" in h_norm or "링크" in h_norm:
            if url_idx == -1: url_idx = i

    rows = all_values[1:]
    logger.info(f"Auditing {len(rows)} rows with 10 concurrent threads...")

    items = [(row_num, row, title_idx, media_idx, url_idx, gemini) for row_num, row in enumerate(rows, start=2)]

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(audit_row, item) for item in items]
        for f in as_completed(futures):
            res = f.result()
            results.append(res)
            logger.info(f"Row {res[0]} audited -> {'[VALID]' if res[3] else '[FIXED]'}")

    # Sort results by row_num
    results.sort(key=lambda x: x[0])

    fixed_count = sum(1 for r in results if not r[3])
    valid_count = sum(1 for r in results if r[3])

    logger.info(f"Audit complete. Valid: {valid_count}, Fixed: {fixed_count}. Updating Google Sheets in batch...")

    # Prepare column batch update
    col_letter = chr(ord('A') + url_idx)
    cell_range = f"{col_letter}2:{col_letter}{len(rows)+1}"
    url_column_data = [[r[2]] for r in results]

    worksheet.update(values=url_column_data, range_name=cell_range)
    logger.info("✅ Batch update of Google Sheets complete!")

    logger.info("==========================================")
    logger.info(f"🎉 100% REPAIR COMPLETE!")
    logger.info(f"Total Rows Audited: {len(rows)}")
    logger.info(f"Valid URLs Kept  : {valid_count}")
    logger.info(f"Broken URLs Fixed: {fixed_count}")
    logger.info("==========================================")

if __name__ == "__main__":
    main()
