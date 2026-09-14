import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.sheets_client import SheetsClient

url_030 = "https://n.news.naver.com/mnews/article/030/0003461589?sid=105"
title = "국가AI위원회 출범... 'AI 3대 강국(G3)' 도약 선언"
media = "전자신문"

resp = requests.get(url_030, headers={'User-Agent': 'Mozilla/5.0'})
resp.encoding = resp.apparent_encoding or 'utf-8'
cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', resp.text, flags=re.DOTALL | re.IGNORECASE)
cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
clean_text = re.sub(r'\s+', ' ', clean_text).strip()

auditor = GPTNewsAuditor()
res = auditor.audit_news_page(title, media, clean_text)

print("ETNews Naver link audit:")
print(" Approved:", res.get("approved"))
print(" Reason:", res.get("reason"))

if res.get("approved"):
    sheets = SheetsClient()
    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    ws.update_cell(15, 7, url_030)
    print("Updated G15 with ETNews Naver Link:", url_030)
