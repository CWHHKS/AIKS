import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import logging

logging.basicConfig(level=logging.INFO)

from services.url_resolver import is_valid_deep_link, resolve_exact_news_url

title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"

bad_url = "https://www.etnews.com/20240502000213" # EV Battery article / WAF block
good_url = "https://www.aitimes.kr/news/articleView.html?idxno=31085" # Exact Samsung SDS FabriX article

print("--- Testing BAD URL (EV Battery) ---")
res_bad = is_valid_deep_link(bad_url, title=title, media=media)
print(f"Bad URL Is Valid? {res_bad} (Expected: False)")

print("\n--- Testing GOOD URL (User's AI Times article) ---")
res_good = is_valid_deep_link(good_url, title=title, media="인공지능신문")
print(f"Good URL Is Valid? {res_good} (Expected: True)")
