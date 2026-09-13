import os
import sys
import json
import logging
import urllib.parse
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from duckduckgo_search import DDGS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.sheets_client import SheetsClient
from services.gemini_client import GeminiClient

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
    if "google.com/search" in url.lower():
        return False  # We prefer exact direct article URLs over search query links
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    if url.lower() in ["none", "#", "null"]:
        return False
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=4, allow_redirects=True, stream=True)
        all_urls = [resp.url.lower()] + [h.url.lower() for h in resp.history]
        for u in all_urls:
            if "/error" in u or "404" in u or "notfound" in u:
                return False
        if resp.status_code == 200:
            return True
    except Exception:
        pass

    return False

from services.url_resolver import resolve_exact_news_url, is_valid_deep_link

def get_best_url(title: str, media: str, current_url: str, gemini_client: GeminiClient) -> str:
    return resolve_exact_news_url(title, media, current_url)

def audit_row(item):
    row_num, row, title_idx, media_idx, url_idx, gemini = item
    title = row[title_idx] if title_idx < len(row) else ""
    media = row[media_idx] if media_idx < len(row) else ""
    current_url = row[url_idx] if url_idx < len(row) else ""

    best_url = get_best_url(title, media, current_url, gemini)
    was_valid = (best_url == current_url)
    return row_num, current_url, best_url, was_valid

def main():
    logger.info("🚀 Starting direct deep-link resolution for news URLs in Google Sheets...")
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
    logger.info(f"Resolving direct deep-links for {len(rows)} rows...")

    items = [(row_num, row, title_idx, media_idx, url_idx, gemini) for row_num, row in enumerate(rows, start=2)]

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(audit_row, item) for item in items]
        for f in as_completed(futures):
            res = f.result()
            results.append(res)
            logger.info(f"Row {res[0]} -> {'[EXACT DEEP-LINK]' if res[2].startswith('http') and 'google.com/search' not in res[2] else '[SEARCH FALLBACK]'}")

    results.sort(key=lambda x: x[0])

    fixed_count = sum(1 for r in results if not r[3])
    valid_count = sum(1 for r in results if r[3])

    logger.info(f"Audit complete. Valid: {valid_count}, Fixed: {fixed_count}. Updating Google Sheets...")

    col_letter = chr(ord('A') + url_idx)
    cell_range = f"{col_letter}2:{col_letter}{len(rows)+1}"
    url_column_data = [[r[2]] for r in results]

    worksheet.update(values=url_column_data, range_name=cell_range)
    logger.info("✅ Direct deep-links batch update of Google Sheets complete!")

if __name__ == "__main__":
    main()
