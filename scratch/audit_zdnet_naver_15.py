import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.sheets_client import SheetsClient

url_092 = "https://n.news.naver.com/mnews/article/092/0002344584?sid=105" # ZDNet Korea
headline_title = "Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B"
media_name = "ZDNet Korea"

resp = requests.get(url_092, headers={'User-Agent': 'Mozilla/5.0'})
resp.encoding = resp.apparent_encoding or 'utf-8'
cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', resp.text, flags=re.DOTALL | re.IGNORECASE)
cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
clean_text = re.sub(r'\s+', ' ', clean_text).strip()

auditor = GPTNewsAuditor()
res = auditor.audit_news_page(headline_title, media_name, clean_text)

print("ZDNet Korea Naver link audit for Item 15:")
print(" Approved:", res.get("approved"))
print(" Reason:", res.get("reason"))

if res.get("approved"):
    sheets = SheetsClient()
    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    ws.update_cell(16, 7, url_092)
    print("Updated G16 with ZDNet Korea Naver Link:", url_092)
