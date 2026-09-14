import sys
from datetime import date
from services.validator import validate_article

print("Testing validator.py with problem URLs...")

test_urls = [
    ("https://namu.wiki/w/%EC%82%BC%EC%84%B1", "삼성SDS", "INVALID_URL_PATTERN"),
    ("https://www.anthropic.com/", "Anthropic", "INVALID_URL_PATTERN"),
    ("https://corporate.jcpenney.com/", "JCPenney", "DOMAIN_NOT_ALLOWED"),
    ("https://www.google.com/search?q=ZDNet+Korea", "ZDNet", "INVALID_URL_PATTERN"),
]

all_passed = True
for url, source, expected_reason in test_urls:
    res = validate_article(url, source_media=source)
    print(f"URL: {url}")
    print(f" -> Passed: {res['passed']}, Reason: {res['reason']} (Expected: {expected_reason})")
    if res['reason'] != expected_reason:
        print(f"[FAIL] MISMATCH! Expected {expected_reason}, got {res['reason']}")
        all_passed = False
    else:
        print("[PASS] Match!")
    print("-" * 50)

if all_passed:
    print("All rejection pattern test cases passed successfully!")
else:
    print("Some test cases failed.")
