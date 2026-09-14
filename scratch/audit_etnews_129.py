import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link

target_url = "https://www.etnews.com/20240502000129"
title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"

print(f"Testing URL: {target_url}", flush=True)
resp = requests.get(target_url, headers={'User-Agent': 'Mozilla/5.0'})
resp.encoding = resp.apparent_encoding or 'utf-8'
raw_html = resp.text
cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
clean_text = re.sub(r'\s+', ' ', clean_text).strip()

print("Extracted text snippet (first 300 chars):", flush=True)
print(clean_text[:300], flush=True)

auditor = GPTNewsAuditor()
audit_res = auditor.audit_news_page(title, media, clean_text)
print("\nGPT Audit Result:", flush=True)
print("Approved:", audit_res.get("approved"), flush=True)
print("Reason:", audit_res.get("reason"), flush=True)

valid = is_valid_deep_link(target_url, title=title, media=media)
print(f"\nFinal is_valid_deep_link result: {valid}", flush=True)
