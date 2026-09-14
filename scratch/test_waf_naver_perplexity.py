import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

def test_modules():
    print("=== 1. Testing Naver Search Module ===")
    from services.naver_search import get_naver_news_candidates
    nv_candidates = get_naver_news_candidates("AI 에이전트", display=3)
    print(f"Naver Candidates Count: {len(nv_candidates)}")
    for i, item in enumerate(nv_candidates, 1):
        print(f"[{i}] {item.get('title')[:30]}... | Media: {item.get('source_media')} | URL: {item.get('source_url')}")
        print(f"    Refs: {item.get('reference_urls')}")

    print("\n=== 2. Testing Perplexity Client Module ===")
    from services.perplexity_client import PerplexityNewsClient
    px = PerplexityNewsClient()
    print(f"Perplexity API Available: {px.is_available()}")

    print("\n=== 3. Testing URL Resolver & WAF Bypass Fallback ===")
    from services.url_resolver import resolve_via_naver_fallback, is_valid_deep_link
    res_url = resolve_via_naver_fallback("생성형 AI 기술 동향", media="전자신문")
    print(f"Resolved Naver WAF Fallback URL: {res_url}")

if __name__ == "__main__":
    test_modules()
