import os
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from typesafe_sdk import TypeSafeClient, Noul, Choice, Score
    TYPESAFE_SDK_AVAILABLE = True
except ImportError:
    TYPESAFE_SDK_AVAILABLE = False
    logger.warning("[JEV/TypeSafe] typesafe-sdk is not installed. Fallback mode enabled.")

class TypeSafeNewsClassifier:
    """
    Jev (TypeSafe System One) News Classifier & Filtering Service for AIKA.
    Performs fast, probabilistic filtering, category routing, and impact scoring.
    """

    ALLOWED_CATEGORIES = [
        "LLM/Agent",
        "Computer Vision",
        "AI Security",
        "Multimodal",
        "AI Hardware/Chip",
        "Gov/Policy AI",
        "General AI"
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY")
        if not self.api_key:
            logger.warning("[JEV/TypeSafe] No TYPESAFE_API_KEY found in environment. Fallback mode will be used.")

    def is_available(self) -> bool:
        """Check if TypeSafe SDK and API key are ready for use."""
        return TYPESAFE_SDK_AVAILABLE and bool(self.api_key)

    def evaluate_article(self, title: str, text: str, min_ai_prob_threshold: float = 0.65) -> Dict[str, Any]:
        """
        Evaluates a single news article using Jev System One questions:
        1. is_ai_news: Noul (Probability this is valid AI technology/product news)
        2. is_within_48h: Noul (Probability this news is breaking news from the past 48 hours)
        3. article_region: Choice (Domestic | Overseas)
        4. article_type: Choice (News | Solution)
        5. primary_category: Choice (Primary category from ALLOWED_CATEGORIES)
        6. korea_relevance: Choice (High | Medium | Low relevance to Korean AI market)
        7. impact_score: Score (1 to 5 strategic impact score)
        """
        if not self.is_available():
            logger.info("[JEV/TypeSafe] SDK/Key unavailable. Returning default fallback evaluation.")
            return self._get_fallback_evaluation()

        content_snippet = f"Title: {title}\nContent:\n{text[:1500]}"

        # Pre-check for WAF / Firewall / Access Denied block patterns
        waf_block_patterns = [
            "web firewall", "firewall security", "access denied", "403 forbidden",
            "cloudflare", "security check", "captcha", "방화벽", "접근이 차단",
            "페이지를 찾을 수 없습니다", "robot check", "page not found", "service unavailable"
        ]
        snippet_lower = text.lower()
        if any(pat in snippet_lower for pat in waf_block_patterns) or len(text.strip()) < 50:
            logger.warning(f"[JEV/TypeSafe] Article '{title}' REJECTED due to WAF/Firewall block or unparsable empty body text.")
            return {
                "is_ai_news": False,
                "ai_probability": 0.0,
                "recency_probability": 0.0,
                "article_region": "국내",
                "article_type": "소식",
                "target_bucket": "국내 AI 소식",
                "primary_category": "General AI",
                "korea_relevance": "Low",
                "impact_score": 1.0,
                "filter_reason": "WAF Firewall access block or unparsable body text detected",
                "status": "success"
            }

        category_criteria = {cat: None for cat in self.ALLOWED_CATEGORIES}

        try:
            with TypeSafeClient(api_key=self.api_key) as client:
                res = client.system_one(
                    state={"article": content_snippet},
                    questions={
                        "is_ai_news": Noul(
                            instructions="Is this document a valid, authentic AI (Artificial Intelligence) technology, model release, product launch, research, or industry news article?"
                        ),
                        "is_valid_content": Noul(
                            instructions="Is this text readable, authentic news body content? Answer FALSE if this text is a web firewall security block, 403 access denied message, Cloudflare check, or broken page error."
                        ),
                        "is_within_48h": Noul(
                            instructions="Does this article present recent breaking news or announcements published within the last 48 hours (not historical or several weeks old)?"
                        ),
                        "article_region": Choice(
                            instructions="Is this article primarily focused on Domestic (Korean AI companies, government policy, Korean market) or Overseas (Global, Silicon Valley, International AI)?",
                            criteria={"Domestic": None, "Overseas": None}
                        ),
                        "article_type": Choice(
                            instructions="Is this article primarily General AI News (industry trend, policy, research, investment) or an AI Solution/Product launch (commercial software, SaaS, API, model release, solution showcase)?",
                            criteria={"News": None, "Solution": None}
                        ),
                        "primary_category": Choice(
                            instructions="Which primary AI category best fits this news article?",
                            criteria=category_criteria
                        ),
                        "korea_relevance": Choice(
                            instructions="What is the level of relevance of this AI news to the Korean AI industry, market, or Korean enterprises?",
                            criteria={"High": None, "Medium": None, "Low": None}
                        ),
                        "impact_score": Score(
                            instructions="Evaluate the overall strategic market impact of this AI news from 1 (routine/minor) to 5 (breaking/major breakthrough).",
                            criteria=[
                                "1 - Minor routine update or niche announcement",
                                "2 - Moderate product feature update or standard release",
                                "3 - Notable industry news with clear market relevance",
                                "4 - Significant AI model launch, partnership, or policy change",
                                "5 - Major AI breakthrough, critical strategic event, or disruptive release"
                            ]
                        )
                    }
                )

            ai_prob = float(res.nouls["is_ai_news"].noul)
            valid_content_prob = float(res.nouls["is_valid_content"].noul)
            recency_prob = float(res.nouls["is_within_48h"].noul)
            is_ai = ai_prob >= min_ai_prob_threshold
            is_valid_content = valid_content_prob >= 0.50
            is_recent = recency_prob >= 0.40  # Soft recency check from Jev

            region_choice = str(res.choices["article_region"].choice)
            type_choice = str(res.choices["article_type"].choice)
            selected_cat = str(res.choices["primary_category"].choice)
            korea_rel = str(res.choices["korea_relevance"].choice)
            imp_score = round(float(res.scores["impact_score"].score), 2)

            # Map region & type to Korean bucket label
            region_label = "국내" if (region_choice == "Domestic" or korea_rel == "High") else "해외"
            type_label = "솔루션" if type_choice == "Solution" else "소식"
            target_bucket = f"{region_label} AI {type_label}"

            filter_reason = None
            if not is_ai:
                filter_reason = f"Low AI relevance probability ({ai_prob:.2f} < {min_ai_prob_threshold})"
            elif not is_valid_content:
                filter_reason = f"Unparsable or WAF blocked content detected by Jev ({valid_content_prob:.2f} < 0.50)"
            elif not is_recent:
                filter_reason = f"Flagged as outdated news (>48h) by Jev recency score ({recency_prob:.2f} < 0.40)"

            logger.info(f"[JEV/TypeSafe] Evaluated: AI_Prob={ai_prob:.2f}, ValidContent={valid_content_prob:.2f}, Bucket={target_bucket}, Score={imp_score}, Pass={is_ai and is_valid_content and is_recent}")

            return {
                "is_ai_news": is_ai and is_valid_content and is_recent,
                "ai_probability": ai_prob,
                "recency_probability": recency_prob,
                "valid_content_probability": valid_content_prob,
                "article_region": region_label,
                "article_type": type_label,
                "target_bucket": target_bucket,
                "primary_category": selected_cat,
                "korea_relevance": korea_rel,
                "impact_score": imp_score,
                "filter_reason": filter_reason,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"[JEV/TypeSafe] Error during System One call: {e}. Falling back to default evaluation.")
            return self._get_fallback_evaluation()

    def _get_fallback_evaluation(self) -> Dict[str, Any]:
        """Provides default values if Jev API call cannot be completed."""
        return {
            "is_ai_news": True,
            "ai_probability": 1.0,
            "recency_probability": 1.0,
            "article_region": "국내",
            "article_type": "소식",
            "target_bucket": "국내 AI 소식",
            "primary_category": "General AI",
            "korea_relevance": "Medium",
            "impact_score": 3.0,
            "filter_reason": None,
            "status": "fallback"
        }
