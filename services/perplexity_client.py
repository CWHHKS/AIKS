import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

logger = logging.getLogger(__name__)

class PerplexityNewsClient:
    """Client for Perplexity AI Real-Time Search API."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY", "")
        self.base_url = "https://api.perplexity.ai/chat/completions"

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def test_connection(self) -> bool:
        """Tests if PERPLEXITY_API_KEY is valid."""
        if not self.is_available():
            return False
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key.strip()}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "sonar",
                "messages": [{"role": "user", "content": "hi"}]
            }
            resp = requests.post(self.base_url, headers=headers, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Perplexity test connection failed: {e}")
            return False

    def search_news_candidates(
        self,
        topic: str,
        research_date: str = "",
        max_results: int = 5,
        model_name: str = "sonar",
        custom_directive: str = "",
        skill_preset: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Uses Perplexity AI online search (sonar or sonar-pro) to discover latest AI news and return articles with citations.
        """
        if not self.is_available():
            logger.info("PERPLEXITY_API_KEY not configured. Skipping Perplexity AI search.")
            return []

        # Validate model_name
        valid_model = model_name if model_name in ["sonar", "sonar-pro", "sonar-reasoning", "sonar-reasoning-pro"] else "sonar"

        date_clause = f"Date: {research_date}" if research_date else "latest AI news from the past 24-48 hours"
        directive_clause = f"\n[USER DIRECTIVES & SKILL RULES]\n- Skill: {skill_preset}\n- Directive: {custom_directive}" if (custom_directive or skill_preset) else ""

        prompt = f"""Search the latest real-time AI news about: '{topic}'. {date_clause}.{directive_clause}
Return a JSON array of up to {max_results} news candidates.
Each candidate object must strictly include:
- "title": English article title
- "korean_title": Natural Korean translation of headline
- "source_media": Official media outlet name (e.g., TechCrunch, Reuters, ZDNet, ETNews)
- "source_url": Direct article working URL starting with https://
- "summary": 2-sentence summary in Korean
- "reference_urls": Array of at least 3 distinct media outlet reference URLs covering this exact headline

Output ONLY valid JSON array inside ```json ``` codeblock.
"""
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": valid_model,
            "messages": [
                {"role": "system", "content": "You are a real-time AI news intelligence auditor."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        try:
            logger.info(f"Calling Perplexity API model '{valid_model}' for topic '{topic}'...")
            resp = requests.post(self.base_url, headers=headers, json=payload, timeout=25)
            if resp.status_code != 200:
                logger.warning(f"Perplexity API ({valid_model}) returned HTTP {resp.status_code}: {resp.text[:200]}")
                return []

            res_data = resp.json()
            choices = res_data.get("choices", [])
            citations = res_data.get("citations", [])

            if not choices:
                return []

            content = choices[0].get("message", {}).get("content", "")
            
            # Extract JSON block
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content.strip()

            candidates = json.loads(json_str)
            if isinstance(candidates, dict) and "candidates" in candidates:
                candidates = candidates["candidates"]

            if not isinstance(candidates, list):
                return []

            # Attach top-level citations to candidates if reference_urls missing or short
            for c in candidates:
                c["discovery_channel"] = f"perplexity_{valid_model}"
                refs = c.get("reference_urls", [])
                if not isinstance(refs, list):
                    refs = []
                for cite in citations:
                    if cite and isinstance(cite, str) and cite.startswith("http") and cite not in refs:
                        refs.append(cite)
                c["reference_urls"] = refs

            logger.info(f"Perplexity AI ({valid_model}) returned {len(candidates)} news candidates with {len(citations)} citations.")
            return candidates
        except Exception as e:
            logger.warning(f"Perplexity API news search exception: {e}")
            return []

