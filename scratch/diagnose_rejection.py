import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from services.gemini_client import GeminiClient
from services.url_resolver import resolve_exact_news_url

def test_discovery_audit():
    gc = GeminiClient()
    batch_params = {
        "batch_id": "TEST-DIAGNOSE",
        "primary_category": "AI 에이전트",
        "news_topic": "AI Industry Trends",
        "target_count": 5,
        "research_date": "2026-09-14",
        "since_date": "2026-09-01",
        "preferred_sources": "zdnet.co.kr, etnews.com"
    }

    res = gc.run_tri_engine_discovery(batch_params, [])
    candidates = res.get("candidates", [])
    print(f"\nTotal Candidates from Tri-Engine: {len(candidates)}")

    for idx, c in enumerate(candidates, 1):
        title = c.get("title")
        media = c.get("source_media")
        raw_url = c.get("source_url")
        refs = c.get("reference_urls", [])
        
        print(f"\n--- Candidate [{idx}] ---")
        print(f"Title: {title[:35] if title else 'No Title'}...")
        print(f"Source Media: {media}")
        print(f"Source URL: {raw_url}")
        
        resolved = resolve_exact_news_url(title, media, raw_url, reference_urls=refs)
        print(f"Resolved URL: {resolved}")
        if resolved:
            print("Status: APPROVED (Verified 200 OK & Dynamic Enrichment / Vendor Approved)")
        else:
            print("Status: REJECTED")

if __name__ == "__main__":
    test_discovery_audit()
