import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link
from services.sheets_client import SheetsClient

url = "https://www.aitimes.kr/news/articleView.html?idxno=31085"
title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "인공지능신문" # AI Times KR

print(f"Fetching user-provided URL: {url}")
resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
resp.encoding = resp.apparent_encoding or 'utf-8'
raw_html = resp.text

cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
clean_text = re.sub(r'\s+', ' ', clean_text).strip()

# Extract title tag
m = re.search(r'<title>(.*?)</title>', raw_html, re.IGNORECASE | re.DOTALL)
page_title = m.group(1).strip() if m else "No Title"

print("Page Title:", page_title)
print("\nClean Text Snippet (first 400 chars):")
print(clean_text[:400])

auditor = GPTNewsAuditor()
res = auditor.audit_news_page(title, media, clean_text)
print("\nGPT Audit Result:")
print("Approved:", res.get("approved"))
print("Reason:", res.get("reason"))

is_valid = is_valid_deep_link(url, title=title, media=media)
print(f"\nis_valid_deep_link: {is_valid}")

# Update Google Sheet G13 with exact user URL!
SPREADSHEET_ID = "1t1n71PXIs1rSTPha6pf5ugwbZ0a5fq44m1K7xg1KXfE"
sheets = SheetsClient()
ws = sheets.news_spreadsheet.worksheet("06_News_All")
ws.update_cell(13, 7, url)
print("\nUpdated Google Sheet Row 13 (G13) with exact URL:", url)
