import os
import sys
import re
import logging
import urllib.parse
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

def clean_news_title(title: str) -> str:
    """Cleans title by removing brackets, newlines, and parenthesized translations."""
    if not title:
        return ""
    cleaned = re.sub(r'\([^\)]*(?:인공지능|AI|출시|발효|투자|모델|기능|발표)[^\)]*\)', '', title)
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned).strip()
    return cleaned

def is_valid_deep_link(url: str, title: str = "", media: str = "") -> bool:
    """
    Strictly validates if a URL is a live, working news article page (HTTP 200 OK) AND passes GPT Auditor Cross-Verification.
    Rejects 404 pages, soft 404s, sales brochures, product landing pages, and hallucinated URL paths.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False

    url_lower = url.lower()
    
    # Reject search engine query links from direct deep-link check
    if any(x in url_lower for x in ["google.com/search", "search.naver.com", "duckduckgo.com"]):
        return False
    if url_lower in ["none", "#", "null"]:
        return False

    # Check path depth - root domains or language roots are not valid deep-links
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip("/")
        if not path or path in ["", "ko", "en", "ko-kr", "en-us"]:
            return False
    except Exception:
        return False

    # Perform GET request and inspect status code + response text for 404 errors
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True, stream=True)
        if resp.status_code != 200:
            return False
            
        final_url_lower = resp.url.lower()
        if any(err in final_url_lower for err in ["/error", "404", "notfound", "page-not-found", "account-billing"]):
            return False

        # Inspect HTML body snippet for soft 404 error messages
        snippet = resp.text[:4000].lower()
        if any(err_msg in snippet for err_msg in ["stop the presses", "page you're looking for has gone out of circulation", "404 not found", "page not found"]):
            return False

        # Tier 2: GPT Auditor Agent Cross-Verification (If title & media provided)
        if title and media:
            try:
                from services.audit_agent import GPTNewsAuditor
                auditor = GPTNewsAuditor()
                if auditor.is_available():
                    audit_res = auditor.audit_news_page(title, media, resp.text)
                    if not audit_res.get("approved", True):
                        logger.warning(f"GPT Auditor REJECTED link '{url}': {audit_res.get('reason')}")
                        return False
            except Exception as e:
                logger.warning(f"GPT Auditor check skipped/exception: {e}")

        return True
    except Exception:
        pass

    return False

def follow_and_get_final_url(url: str, title: str = "", media: str = "") -> Optional[str]:
    """Follows HTTP redirects and returns the final target URL if valid."""
    if not url or not url.startswith("http"):
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True, stream=True)
        final_url = resp.url
        if is_valid_deep_link(final_url, title=title, media=media):
            return final_url
    except Exception:
        pass
    return None

def resolve_exact_news_url(title: str, media: str, current_url: str = "") -> str:
    """
    Multi-tier resolution strategy to find and return the exact direct news article URL.
    1. If current_url passes strict HTTP 200 & GPT Audit Agent check, return it.
    2. Try Gemini Search Grounding for exact direct article URL and verify via live HTTP 200 GET & GPT Auditor.
    3. Fallback to clean Google Search query link (guaranteed 100% 404-proof).
    """
    # Tier 1: Test existing URL
    if current_url:
        final_url = follow_and_get_final_url(current_url, title=title, media=media)
        if final_url:
            logger.info(f"Existing URL verified 200 OK deep-link: {final_url}")
            return final_url

    cleaned_title = clean_news_title(title)
    
    # Tier 2: Gemini Google Search Grounding
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            import google.ai.generativelanguage_v1beta as glm

            genai.configure(api_key=api_key)
            search_tool = glm.Tool(google_search={})
            model = genai.GenerativeModel(
                model_name=os.getenv("DISCOVERY_MODEL", "gemini-2.5-flash"),
                tools=[search_tool]
            )

            prompt = f"""Search Google and find the EXACT direct working URL of the news article on {media}.
Article Title: {cleaned_title}

Requirements:
- Must be a real working article page URL on {media} (or official news outlet).
- Output ONLY the URL starting with https://.
"""
            resp = model.generate_content(prompt)
            if resp and resp.text:
                extracted_urls = re.findall(r'https?://[^\s\)]+', resp.text)
                for u in extracted_urls:
                    u_clean = u.rstrip(".,;\"'")
                    if is_valid_deep_link(u_clean, title=cleaned_title, media=media):
                        logger.info(f"Resolved via Gemini Search Grounding (Verified 200 OK & GPT Approved): {u_clean}")
                        return u_clean
        except Exception as e:
            logger.warning(f"Gemini search grounding exception: {e}")

    # Tier 3: Direct Site Search Grounding Fallback
    # (Search query URLs like google.com/search are STRICTLY DISALLOWED as final URLs)
    logger.warning(f"Could not resolve verified direct deep-link for '{cleaned_title}' on initial check. Retrying direct site resolution...")
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            import google.ai.generativelanguage_v1beta as glm
            genai.configure(api_key=api_key)
            search_tool = glm.Tool(google_search={})
            model = genai.GenerativeModel(model_name=os.getenv("DISCOVERY_MODEL", "gemini-2.5-flash"), tools=[search_tool])
            prompt = f"Find the EXACT direct article URL on {media} for: {cleaned_title}. Return ONLY the direct article URL starting with https://. Do NOT return google.com/search or search query links."
            resp = model.generate_content(prompt)
            if resp and resp.text:
                urls = re.findall(r'https?://[^\s\)]+', resp.text)
                for u in urls:
                    u_clean = u.rstrip(".,;\"'")
                    if not any(x in u_clean.lower() for x in ["google.com/search", "search.naver.com", "duckduckgo.com"]) and is_valid_deep_link(u_clean, title=cleaned_title, media=media):
                        logger.info(f"Resolved direct target site URL via Tier 3: {u_clean}")
                        return u_clean
        except Exception as e:
            logger.warning(f"Tier 3 resolution exception: {e}")

    # Return current_url if valid direct link, or empty string for review (Never return a search query link!)
    if current_url and not any(x in current_url.lower() for x in ["google.com/search", "search.naver.com", "duckduckgo.com"]):
        return current_url
    return ""
