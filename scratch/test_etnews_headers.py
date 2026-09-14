import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link

url = "https://www.etnews.com/20240502000209"
title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.etnews.com/',
    'Connection': 'keep-alive'
}

resp = session.get(url, headers=headers)
resp.encoding = resp.apparent_encoding or 'utf-8'
raw_html = resp.text
cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
clean_text = re.sub(r'\s+', ' ', clean_text).strip()

print("Snippet:", clean_text[:400])

auditor = GPTNewsAuditor()
res = auditor.audit_news_page(title, media, clean_text)
print("AUDIT APPROVED?", res.get("approved"))
print("AUDIT REASON:", res.get("reason"))
