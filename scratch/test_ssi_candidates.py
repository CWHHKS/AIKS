import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.sheets_client import SheetsClient

headline_title = "Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B"
media_name = "TechCrunch"

candidates = [
    "https://n.news.naver.com/mnews/article/015/0005029381?sid=104", # 한국경제
    "https://n.news.naver.com/mnews/article/001/0014912345?sid=104", # 연합뉴스
    "https://n.news.naver.com/mnews/article/092/0002344840?sid=105", # ZDNet Korea
    "https://techcrunch.com/2024/09/04/ilya-sutskevers-safe-superintelligence-raises-1b/"
]

auditor = GPTNewsAuditor()
verified_url = None

for url in candidates:
    print(f"\nTesting Candidate URL: {url}", flush=True)
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
        print(f" Status: {r.status_code}", flush=True)
        if r.status_code == 200:
            r.encoding = r.apparent_encoding or 'utf-8'
            cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', r.text, flags=re.DOTALL | re.IGNORECASE)
            cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            res = auditor.audit_news_page(headline_title, media_name, clean_text)
            print(f" Approved: {res.get('approved')}, Reason: {res.get('reason')}", flush=True)
            if res.get('approved'):
                verified_url = url
                print(f"\n SUCCESS! Found 100% Verified Link for Item 15:\n {verified_url}", flush=True)
                break
    except Exception as e:
        print(f" Exception: {e}", flush=True)

if verified_url:
    sheets = SheetsClient()
    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    ws.update_cell(16, 7, verified_url)
    print("Updated Google Sheet Row 16 Cell G16 with verified URL!", flush=True)
