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

resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
resp.encoding = resp.apparent_encoding or 'utf-8'
raw_html = resp.text
cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
clean_text = re.sub(r'\s+', ' ', clean_text).strip()

auditor = GPTNewsAuditor()
res = auditor.audit_news_page(title, media, clean_text)
print("AUDIT APPROVED?", res.get("approved"))
print("AUDIT REASON:", res.get("reason"))

is_valid = is_valid_deep_link(url, title=title, media=media)
print("IS VALID DEEP LINK?", is_valid)
