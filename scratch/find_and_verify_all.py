import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import urllib.request
import urllib.parse
import re
from bs4 import BeautifulSoup
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link

title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"

# 1. Search Naver news for "삼성SDS 패브릭스 출시"
query = "삼성SDS 패브릭스 출시"
url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'})

links_to_test = []
try:
    resp = urllib.request.urlopen(req)
    html = resp.read().decode('utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if href.startswith('http') and not any(x in href for x in ['naver.com/search', 'search.naver']):
            if any(domain in href for domain in ['etnews.com', 'zdnet.co.kr', 'chosun.com', 'hankyung.com', 'yna.co.kr', 'news.naver.com', 'bloter.net', 'ddaily.co.kr']):
                if href not in links_to_test:
                    links_to_test.append(href)
except Exception as e:
    print("Error fetching Naver search:", e, flush=True)

print(f"Collected {len(links_to_test)} candidate links from Naver search:", flush=True)
for l in links_to_test:
    print(" -", l, flush=True)

verified_url = None
auditor = GPTNewsAuditor()

for link in links_to_test:
    print(f"\nEvaluating link: {link}", flush=True)
    try:
        req_link = urllib.request.Request(link, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        resp = urllib.request.urlopen(req_link, timeout=5)
        raw_html = resp.read().decode('utf-8', errors='ignore')
        
        cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        res = auditor.audit_news_page(title, media, clean_text)
        print(f"Audit result for {link}: Approved={res.get('approved')}, Reason={res.get('reason')}", flush=True)
        if res.get('approved'):
            verified_url = link
            print(f"\n SUCCESS! Found 100% Verified Deep Link: {verified_url}", flush=True)
            break
    except Exception as e:
        print(f"Failed to fetch/audit {link}: {e}", flush=True)

if not verified_url:
    print("\nNo verified URL found in initial list.", flush=True)
