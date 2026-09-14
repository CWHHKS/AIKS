import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link

title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"

# Let's test Naver ETNews & ZDNet candidate links
candidates = [
    "https://n.news.naver.com/mnews/article/030/0003202976",
    "https://n.news.naver.com/mnews/article/030/0003202975",
    "https://n.news.naver.com/mnews/article/092/0002329971",
    "https://zdnet.co.kr/view/?no=20240502104523",
    "https://zdnet.co.kr/view/?no=20240502103000"
]

for url in candidates:
    print(f"\n--- Testing: {url} ---")
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    if resp.status_code == 200:
        resp.encoding = resp.apparent_encoding or 'utf-8'
        raw_html = resp.text
        cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        print("Snippet:", clean_text[:200])

        auditor = GPTNewsAuditor()
        res = auditor.audit_news_page(title, media, clean_text)
        print("Approved:", res.get("approved"))
        print("Reason:", res.get("reason"))
