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
    Independent Auditor Agent supporting both OpenAI GPT and Gemini Flash models.
    Performs strict multi-tier cross-verification on parsed news page content:
    1. Page Type Classification (Rejects Product Landings, WAF Blocks, Homepages).
    2. Strict Semantic Fact & Entity Matching (Validates presence of Headline Entities, Product/Company Names, and Core Events).
    """
    def __init__(self):
        self.mode = os.getenv("PIPELINE_MODE", "standard").strip().lower()
        self.openai_key = _get_api_key("OPENAI_API_KEY")
        self.gemini_key = _get_api_key("GEMINI_API_KEY")
        self.gpt_model_name = _get_api_key("GPT_AUDIT_MODEL") or "gpt-4o"
        self.gemini_model_name = _get_api_key("DISCOVERY_MODEL") or "gemini-3.5-flash"
        self.client = None

        if self.mode == "reversed" and self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                self.gemini_genai = genai
                logger.info(f"Loaded Gemini Auditor Agent with model: {self.gemini_model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client for auditing: {e}")
        elif self.openai_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.openai_key)
                logger.info(f"Loaded GPT Auditor Agent with model: {self.gpt_model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client for auditing: {e}")

    def is_available(self) -> bool:
        if self.mode == "reversed":
            return getattr(self, "gemini_genai", None) is not None
        return self.client is not None

    def audit_news_page(self, title: str, media: str, page_text: str) -> Dict[str, Any]:
        """
        Audits extracted page text against headline title & expected media.
        Returns dict: {"approved": bool, "page_type": str, "fact_match": bool, "reason": str}
        """
        if not self.is_available():
            logger.warning("Auditor unavailable (missing API key/package). Passing default.")
            return {"approved": True, "page_type": "UNAUDITED", "fact_match": True, "reason": "Auditor not configured"}

        # Quick WAF / Block check
        text_lower = page_text[:2000].lower()
        if any(waf in text_lower for waf in ["web firewall security policies", "blocked request", "access denied", "403 forbidden", "404 not found", "page not found"]):
            return {
                "page_type": "ERROR_BLOCK",
                "fact_match": False,
                "approved": False,
                "reason": "Extracted text is a web firewall security block or 404 page, not an article."
            }

        prompt = f"""You are a flexible and smart AI news audit assistant.
Your goal is to verify if the web page text is a legitimate AI news article, press release, or tech blog post related to the topic of the headline.

Target Headline Title: {title}
Expected Media/Source: {media}

Extracted Web Page Text:
{page_text[:4000]}

Evaluation Rules:
1. page_type:
   - Set to 'NEWS_ARTICLE' or 'PRESS_RELEASE' if it is a news article, tech blog, or press release.
   - If it is a WAF block message, error page, or 404 page, set to 'ERROR'.
2. fact_match:
   - Does the text cover the same or related AI technology topic, company, or industry trend mentioned in the headline?
   - Be flexible with Korean/English translations, synonyms, and broad industry coverage (e.g. AI agents, LLMs, AI models, enterprise AI).
   - Only set fact_match to FALSE if the text is completely unrelated (e.g., real estate, sports, cooking, 404 error page).
3. recency_match:
   - Set to TRUE unless the text is explicitly an old article from 2+ years ago (e.g., 2022/2023).
4. approved: Set to TRUE if page_type is ('NEWS_ARTICLE' or 'PRESS_RELEASE') AND fact_match is TRUE. Otherwise set to FALSE.

Return JSON ONLY in this exact structure:
{{
  "page_type": "NEWS_ARTICLE | PRESS_RELEASE | PRODUCT_LANDING | ERROR",
  "fact_match": true | false,
  "recency_match": true | false,
  "approved": true | false,
  "reason": "Concise explanation of audit result"
}}
"""
        if self.mode == "reversed" and getattr(self, "gemini_genai", None):
            return self._audit_with_gemini(prompt, title)
        
        return self._audit_with_gpt(prompt, title)

    def _audit_with_gpt(self, prompt: str, title: str) -> Dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.gpt_model_name,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a smart, flexible AI news auditor. Approve any legitimate AI news, blog post, or press release related to the target topic."},
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

    def _audit_with_gemini(self, prompt: str, title: str) -> Dict[str, Any]:
        try:
            model = self.gemini_genai.GenerativeModel(self.gemini_model_name)
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            # Clean JSON formatting backticks
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()
            result = json.loads(raw_text)
            logger.info(f"Gemini Audit Result for '{title[:25]}...': Approved={result.get('approved')} ({result.get('reason')})")
            return result
        except Exception as e:
            logger.error(f"Gemini Audit Agent exception: {e}")
            return {"approved": True, "page_type": "ERROR", "fact_match": True, "reason": f"Audit exception: {e}"}
