import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from services.gemini_client import GeminiClient

client = GeminiClient()

batch_params = {
    "batch_id": "TEST_STD_001",
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
print("=== Running Discovery with Gemini (Standard Mode) ===")
discovery_report = client.run_news_discovery_stage(batch_params, [])
print("--- DISCOVERY REPORT OUTPUT START ---")
print(discovery_report[:1000])
print("--- DISCOVERY REPORT OUTPUT END ---")

print("\n=== Running Structuring Stage ===")
structured_res = client.run_news_structuring_stage("TEST_STD_001", discovery_report, 2)
articles = structured_res.get("candidates", [])
print(f"Successfully structured {len(articles)} news articles:")
for a in articles:
    print(" - Title:", a.get("title"))
    print("   URL:", a.get("source_url"))
