import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import logging
logging.basicConfig(level=logging.INFO)

from services.url_resolver import resolve_exact_news_url

test_cases = [
    {
        "title": "국가AI위원회 출범... 'AI 3대 강국(G3)' 도약 선언",
        "media": "전자신문",
        "url": "https://www.etnews.com/20240926000276" # WAF blocked
    },
    {
        "title": "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시",
        "media": "전자신문",
        "url": "https://www.etnews.com/20240502000213" # WAF blocked / battery article
    },
    {
        "title": "Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B",
        "media": "TechCrunch",
        "url": "https://www.etnews.com/20240325000212" # WAF blocked / mismatched
    }
]

print("=== TESTING UPGRADED URL RESOLVER ===")
for idx, tc in enumerate(test_cases, 1):
    print(f"\n[{idx}] Title: {tc['title']}")
    print(f"    Media: {tc['media']}")
    print(f"    Old URL: {tc['url']}")
    res = resolve_exact_news_url(tc['title'], tc['media'], tc['url'])
    print(f"    -> RESOLVED URL: {res}")
