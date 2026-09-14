import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from services.gemini_client import GeminiClient, SafeDict

client = GeminiClient()

batch_params = {
    "batch_id": "TEST_001",
    "primary_category": "All",
    "news_topic": "All",
    "language": "All (EN + KO)",
    "target_count": 2,
    "research_date": "2026-09-14",
    "since_date": "2026-08-17",
    "preferred_sources": "zdnet.co.kr, etnews.com",
    "existing_urls": []
}

os.environ["PIPELINE_MODE"] = "reversed"
print("=== Running Discovery with GPT-4o (Reversed Mode) ===")
discovery_report = client.run_news_discovery_stage(batch_params, [])
print("--- DISCOVERY REPORT OUTPUT START ---")
print(discovery_report[:2000])
print("--- DISCOVERY REPORT OUTPUT END ---")

print("\n=== Running Structuring Stage ===")
structured_res = client.run_news_structuring_stage("TEST_001", discovery_report, 2)
print("Parsed Articles Count:", len(structured_res.get("articles", [])))
