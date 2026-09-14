import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import re
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link

title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"

candidates = [
    "https://www.etnews.com/20240502000078",
    "https://www.etnews.com/20240502000085",
    "https://www.etnews.com/20240502000100",
    "https://www.etnews.com/20240502000115",
    "https://www.etnews.com/20240502000150",
    "https://www.etnews.com/20240502000200",
    "https://n.news.naver.com/mnews/article/030/0003202976", # 030 = etnews
    "https://zdnet.co.kr/view/?no=20240502104523"
]

for url in candidates:
    print(f"Testing candidate: {url}")
    valid = is_valid_deep_link(url, title=title, media=media)
    print(f"Result for {url}: {valid}\n")
