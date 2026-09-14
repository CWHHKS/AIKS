import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from services.sheets_client import SheetsClient
from services.url_resolver import is_valid_deep_link, resolve_exact_news_url
import requests
import re

sheets = SheetsClient()
ws = sheets.news_spreadsheet.worksheet("06_News_All")
row15 = ws.row_values(15) # Row 15 is Item 14

print("Row 15 values (Item 14):", flush=True)
for idx, val in enumerate(row15, 1):
    print(f" Col {idx}: {val}", flush=True)

# Title is in Col 3 or 4, URL is in Col 7 (G)
headline_title = row15[3] if len(row15) > 3 else ""
media_name = row15[4] if len(row15) > 4 else ""
current_url = row15[6] if len(row15) > 6 else ""

print(f"\nItem 14 Headline: {headline_title}", flush=True)
print(f"Item 14 Media: {media_name}", flush=True)
print(f"Current URL: {current_url}", flush=True)

# Find Naver News deep-link for ETNews article 20240926000276
# ETNews article 000276 on 2024-09-26 corresponds to Naver News press 030 article 0003248386 or similar!
# Let's search Naver news for this exact title
query = headline_title
print(f"\nSearching Naver News for alternative stable link for: {query}")
naver_search_url = f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(query)}"
resp = requests.get(naver_search_url, headers={'User-Agent': 'Mozilla/5.0'})
resp.encoding = 'utf-8'

from bs4 import BeautifulSoup
soup = BeautifulSoup(resp.text, 'html.parser')

naver_links = []
for a in soup.find_all('a'):
    href = a.get('href', '')
    if 'news.naver.com/mnews/article/' in href:
        if href not in naver_links:
            naver_links.append(href)

print("\nFound Naver News Links:")
for nl in naver_links:
    print(" -", nl)

# Also test ETNews Naver article for press 030 ID
etnews_id = "20240926000276"
# Let's test the Naver links with GPT Auditor
from services.audit_agent import GPTNewsAuditor
auditor = GPTNewsAuditor()

best_url = None
for nl in naver_links:
    r = requests.get(nl, headers={'User-Agent': 'Mozilla/5.0'})
    r.encoding = r.apparent_encoding or 'utf-8'
    cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', r.text, flags=re.DOTALL | re.IGNORECASE)
    cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    audit_res = auditor.audit_news_page(headline_title, media_name, clean_text)
    print(f"\nTesting Naver Link: {nl}")
    print(f" Approved: {audit_res.get('approved')}, Reason: {audit_res.get('reason')}")
    if audit_res.get('approved'):
        best_url = nl
        break

if best_url:
    print(f"\n>>> FOUND 100% STABLE VERIFIED NAVER LINK: {best_url}")
    ws.update_cell(15, 7, best_url)
    print("Updated Row 15 Cell G15 with stable Naver deep-link!")
