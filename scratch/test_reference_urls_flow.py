import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from services.gemini_client import GeminiClient
from services.url_resolver import resolve_exact_news_url

client = GeminiClient()

batch_params = {
    "batch_id": "TEST_REF_001",
    "primary_category": "All",
    "news_topic": "All",
    "language": "All (EN + KO)",
    "target_count": 2,
    "research_date": "2026-09-14",
    "since_date": "2026-08-17",
    "preferred_sources": "zdnet.co.kr, etnews.com",
    "existing_urls": []
}

os.environ["PIPELINE_MODE"] = "standard"
print("=== Step 1 & 2: Discovery & Structuring ===")
discovery_report = client.run_news_discovery_stage(batch_params, [])
structured_res = client.run_news_structuring_stage("TEST_REF_001", discovery_report, 2)
articles = structured_res.get("candidates", [])

print(f"\nStructured {len(articles)} articles:")
for idx, a in enumerate(articles, 1):
    title = a.get("title", "")
    title_kr = a.get("korean_title", title)
    media = a.get("source_media", "News")
    raw_url = a.get("source_url", "")
    ref_urls = a.get("reference_urls", [])

    print(f"\n[{idx}] Title: {title_kr}")
    print(f"    Raw URL: {raw_url}")
    print(f"    Reference Candidate URLs ({len(ref_urls)}): {ref_urls}")

    # Step 3: Test URL Resolver with Candidate Reference URLs
    resolved = resolve_exact_news_url(title, media, raw_url, title_kr=title_kr, reference_urls=ref_urls)
    print(f"    Resolved Final Verified URL: {resolved}")
