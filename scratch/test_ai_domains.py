import requests
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.url_resolver import is_valid_deep_link, get_random_headers

domains = [
    "https://www.aitimes.com/",
    "https://www.aitimes.com/news/articleView.html?idxno=163000", # Example deep link format
    "https://www.artificialintelligence-news.com/",
    "https://www.artificialintelligence-news.com/news/example-article"
]

print("=== Testing AI Portals Access & WAF Behavior ===")

for url in domains:
    print(f"\nTesting URL: {url}")
    try:
        headers = get_random_headers()
        res = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        print(f"  - HTTP Status: {res.status_code}")
        print(f"  - Final URL: {res.url}")
        print(f"  - Response Encoding: {res.encoding}")
        print(f"  - Content Length: {len(res.text)} bytes")
        
        # Check snippet for WAF or block
        snippet = res.text[:500].replace("\n", " ")
        print(f"  - Content Snippet: {snippet[:150]}...")
        
        # Test url_resolver validation
        valid = is_valid_deep_link(url)
        print(f"  - is_valid_deep_link: {valid}")
    except Exception as e:
        print(f"  - Error: {e}")
