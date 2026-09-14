import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from services.sheets_client import SheetsClient
from services.audit_agent import GPTNewsAuditor
import requests
import urllib.parse
import re
from bs4 import BeautifulSoup

sheets = SheetsClient()
ws = sheets.news_spreadsheet.worksheet("06_News_All")
row16 = ws.row_values(16) # Row 16 is Item 15

print("Row 16 values (Item 15):", flush=True)
for idx, val in enumerate(row16, 1):
    print(f" Col {idx}: {val}", flush=True)

# Headline is in Col 5 (E), Current URL in Col 7 (G)
headline_title = row16[4] if len(row16) > 4 else ""
media_name = row16[5] if len(row16) > 5 else "전자신문"
old_url = row16[6] if len(row16) > 6 else ""

print(f"\nItem 15 Headline: {headline_title}", flush=True)
print(f"Item 15 Media: {media_name}", flush=True)
print(f"Old WAF URL: {old_url}", flush=True)

# Search Naver news for the exact title
url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(headline_title)}"
print(f"\nSearching Naver News URL: {url}", flush=True)

resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
resp.encoding = 'utf-8'

soup = BeautifulSoup(resp.text, 'html.parser')
candidates = []

for a in soup.find_all('a'):
    href = a.get('href', '')
    if 'n.news.naver.com/mnews/article/' in href:
        if href not in candidates:
            candidates.append(href)

print(f"Found {len(candidates)} Naver article candidates:", flush=True)
for c in candidates[:10]:
    print(f" - {c}", flush=True)

auditor = GPTNewsAuditor()
verified_url = None

# Prioritize ETNews 030 link if present
etnews_naver = [c for c in candidates if '/030/' in c]
other_navers = [c for c in candidates if '/030/' not in c]
ordered_candidates = etnews_naver + other_navers

for c_url in ordered_candidates:
    print(f"\nAuditing Candidate: {c_url}", flush=True)
    r = requests.get(c_url, headers={'User-Agent': 'Mozilla/5.0'})
    r.encoding = r.apparent_encoding or 'utf-8'
    cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', r.text, flags=re.DOTALL | re.IGNORECASE)
    cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    res = auditor.audit_news_page(headline_title, media_name, clean_text)
    print(f" Approved: {res.get('approved')}, Reason: {res.get('reason')}", flush=True)
    if res.get('approved'):
        verified_url = c_url
        print(f"\n SUCCESS! Found 100% Verified Link for Item 15:\n {verified_url}", flush=True)
        break

if verified_url:
    ws.update_cell(16, 7, verified_url)
    print("Updated Google Sheet Row 16 Cell G16 with verified URL!", flush=True)
else:
    print("No verified URL found in candidates list.", flush=True)
