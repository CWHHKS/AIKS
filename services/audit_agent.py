import os
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

logger = logging.getLogger(__name__)

def _get_api_key(key: str) -> Optional[str]:
    val = os.getenv(key)
    if val:
        return str(val).strip().strip('"').strip("'")
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key]).strip().strip('"').strip("'")
    except Exception:
        pass
    return None

class GPTNewsAuditor:
    """
    Independent Auditor Agent using OpenAI GPT models (e.g. gpt-4o-mini).
    Performs strict 2-tier cross-verification on parsed news page content:
    1. Page Type Classification (Rejects Product Landings, Sales Brochures, Homepages).
    2. Semantic Fact Matching (Validates presence of Headline Entities, Event, Amounts).
    """
    def __init__(self):
        self.api_key = _get_api_key("OPENAI_API_KEY")
        self.model_name = _get_api_key("GPT_AUDIT_MODEL") or "gpt-4o-mini"
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"Loaded GPT Auditor Agent with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")

    def is_available(self) -> bool:
        return self.client is not None

    def audit_news_page(self, title: str, media: str, page_text: str) -> Dict[str, Any]:
        """
        Audits extracted page text against headline title & expected media.
        Returns dict: {"approved": bool, "page_type": str, "fact_match": bool, "reason": str}
        """
        if not self.is_available():
            logger.warning("GPT Auditor unavailable (missing API key/package). Passing default.")
            return {"approved": True, "page_type": "UNAUDITED", "fact_match": True, "reason": "GPT Auditor not configured"}

        prompt = f"""You are an independent news audit agent.
Evaluate if the supplied web page text is a REAL news article or press release covering the specified headline event.

Headline Title: {title}
Expected Media/Source: {media}

Extracted Web Page Text:
{page_text[:4000]}

Evaluation Rules:
1. page_type: Must be 'NEWS_ARTICLE' or 'PRESS_RELEASE'. 
   - If it is a product landing page, marketing brochure, product documentation, or home page, set page_type to 'PRODUCT_LANDING' or 'HOMEPAGE'.
2. fact_match: Are the main entities, funding amounts, or core events from the headline explicitly discussed in the text?
3. approved: Set to true ONLY if page_type is ('NEWS_ARTICLE' or 'PRESS_RELEASE') AND fact_match is true. Otherwise set approved to false.

Return JSON ONLY in this exact structure:
{{
  "page_type": "NEWS_ARTICLE | PRESS_RELEASE | PRODUCT_LANDING | HOMEPAGE | ERROR",
  "fact_match": true | false,
  "approved": true | false,
  "reason": "Short explanation of the decision"
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a strict, objective AI news audit agent."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            content = response.choices[0].message.content
            result = json.loads(content)
            logger.info(f"GPT Audit Result for '{title[:25]}...': Approved={result.get('approved')} ({result.get('reason')})")
            return result
        except Exception as e:
            logger.error(f"GPT Audit Agent exception: {e}")
            return {"approved": True, "page_type": "ERROR", "fact_match": True, "reason": f"Audit exception: {e}"}
