import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import urllib.parse
import re
from bs4 import BeautifulSoup
from services.audit_agent import GPTNewsAuditor
from services.sheets_client import SheetsClient

headline_title = "Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B"
media_name = "TechCrunch"

# Search naver news for "세이프 슈퍼인텔리전스" "10억 달러"
query = "세이프 슈퍼인텔리전스 10억 달러"
url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}"

resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
resp.encoding = 'utf-8'

soup = BeautifulSoup(resp.text, 'html.parser')
candidates = []

for item in soup.select('ul.list_news > li'):
    title_tag = item.select_one('a.news_tit')
    if title_tag:
        t_link = title_tag.get('href')
        t_text = title_tag.text.strip()
        navers = item.select('a.info')
        for n in navers:
            n_href = n.get('href', '')
            if 'n.news.naver.com/mnews/article/' in n_href:
                if n_href not in candidates:
                    candidates.append((n_href, t_text))

print(f"Found {len(candidates)} Naver article candidates:", flush=True)
for c in candidates:
    print(f" - {c[0]} | {c[1]}", flush=True)

auditor = GPTNewsAuditor()
verified_url = None

for c_url, c_title in candidates:
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
    sheets = SheetsClient()
    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    ws.update_cell(16, 7, verified_url)
    print("Updated Google Sheet Row 16 Cell G16 with verified URL!", flush=True)
