import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from services.sheets_client import SheetsClient
from services.audit_agent import GPTNewsAuditor
import requests
import urllib.parse
import re
from bs4 import BeautifulSoup

query_str = "국가AI위원회 출범 G3"
title = "국가AI위원회 출범... 'AI 3대 강국(G3)' 도약 선언"
media = "전자신문"

url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query_str)}"
print(f"Searching URL: {url}", flush=True)

resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
resp.encoding = 'utf-8'

soup = BeautifulSoup(resp.text, 'html.parser')
candidates = []

for a in soup.find_all('a'):
    href = a.get('href', '')
    title_text = a.text.strip()
    if 'n.news.naver.com/mnews/article/' in href:
        if href not in [c[0] for c in candidates]:
            candidates.append((href, title_text))

print(f"Found {len(candidates)} Naver article candidates:", flush=True)
for c in candidates[:10]:
    print(f" - {c[0]}", flush=True)

auditor = GPTNewsAuditor()
verified_url = None

for c_url, c_title in candidates:
    print(f"\nAuditing: {c_url}", flush=True)
    r = requests.get(c_url, headers={'User-Agent': 'Mozilla/5.0'})
    r.encoding = r.apparent_encoding or 'utf-8'
    cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', r.text, flags=re.DOTALL | re.IGNORECASE)
    cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    res = auditor.audit_news_page(title, media, clean_text)
    print(f" Approved: {res.get('approved')}, Reason: {res.get('reason')}", flush=True)
    if res.get('approved'):
        verified_url = c_url
        print(f"\n SUCCESS! Found 100% Verified Link for Item 14:\n {verified_url}", flush=True)
        break

if verified_url:
    sheets = SheetsClient()
    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    ws.update_cell(15, 7, verified_url)
    print("Updated Google Sheet Row 15 Cell G15 with verified URL!", flush=True)
