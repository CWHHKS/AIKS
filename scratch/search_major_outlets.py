import requests
import re
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link

title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

test_urls = [
    "https://www.yna.co.kr/view/AKR20240502035400003",
    "https://www.hankyung.com/article/2024050293811",
    "https://biz.chosun.com/it-science/ict/2024/05/02/7QW2J45X5FDLFCD2Q7P7Q5M2LY/"
]

for url in test_urls:
    print(f"\nTesting: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        print("Status code:", resp.status_code)
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding or 'utf-8'
            cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', resp.text, flags=re.DOTALL | re.IGNORECASE)
            cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            auditor = GPTNewsAuditor()
            res = auditor.audit_news_page(title, "News", clean_text)
            print("Audit Approved?", res.get("approved"))
            print("Audit Reason:", res.get("reason"))
            if res.get("approved"):
                print(">>> VERIFIED WORKING DEEP LINK FOUND:", url)
    except Exception as e:
        print("Error:", e)
