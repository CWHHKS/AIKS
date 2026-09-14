import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import logging

logging.basicConfig(level=logging.INFO)

from services.url_resolver import resolve_exact_news_url, is_valid_deep_link
from services.audit_agent import GPTNewsAuditor

title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"
old_url = "https://www.etnews.com/20240502000213"

print("--- Testing Old URL with GPT Auditor ---")
is_valid_old = is_valid_deep_link(old_url, title=title, media=media)
print("Is old URL valid?", is_valid_old)

print("--- Resolving correct URL ---")
new_url = resolve_exact_news_url(title, media, old_url)
print("Resolved URL:", new_url)
