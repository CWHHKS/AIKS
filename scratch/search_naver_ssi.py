import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import re
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from services.audit_agent import GPTNewsAuditor
from services.sheets_client import SheetsClient

headline_title = "Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B"
media_name = "TechCrunch"

query = "세이프 슈퍼인텔리전스 10억"
url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'})

links_to_test = []
try:
    resp = urllib.request.urlopen(req)
    html = resp.read().decode('utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a'):
        href = a.get('href', '')
        title_text = a.text.strip()
        if 'n.news.naver.com/mnews/article/' in href:
            if href not in links_to_test:
                print(f"Candidate: {href} | {title_text[:40]}", flush=True)
                links_to_test.append(href)
except Exception as e:
    print("Naver search error:", e, flush=True)

auditor = GPTNewsAuditor()
verified_url = None

for link in links_to_test:
    print(f"\nAuditing link: {link}", flush=True)
    try:
        req_link = urllib.request.Request(link, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        resp = urllib.request.urlopen(req_link, timeout=5)
        raw_html = resp.read().decode('utf-8', errors='ignore')
        
        cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        res = auditor.audit_news_page(headline_title, media_name, clean_text)
        print(f"Approved: {res.get('approved')}, Reason: {res.get('reason')}", flush=True)
        if res.get('approved'):
            verified_url = link
            print(f"\n SUCCESS! Found 100% Verified Deep Link: {verified_url}", flush=True)
            break
    except Exception as e:
        print(f"Failed to fetch/audit {link}: {e}", flush=True)

if verified_url:
    sheets = SheetsClient()
    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    ws.update_cell(16, 7, verified_url)
    print("Updated Google Sheet Row 16 Cell G16 with verified URL!", flush=True)
