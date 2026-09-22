import re
import time
import json
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, Set
import urllib.parse
import requests
from bs4 import BeautifulSoup

from services.domain_utils import normalize_domain

logger = logging.getLogger("validator")


# Default User-Agent header for HTTP requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 12 Fixed Primary AI Categories (Phase 4 / Enum)
ALLOWED_CATEGORIES = {
    "Generative AI", "AI Agents", "AI Governance", "Data and AI Platform",
    "AI Security", "Conversational AI", "Developer Tools", "Enterprise Automation",
    "AI Chips & Hardware", "AI Infrastructure", "Industry AI", "Other"
}

def calculate_overfetch_count(target_count: int) -> int:
    """
    Calculates candidate discovery count:
    - If target_count <= 5: target_count + 2 (e.g. 5 -> 7)
    - If target_count > 5: ceil(target_count * 1.3) (e.g. 10 -> 13)
    """
    import math
    if target_count <= 5:
        return target_count + 2
    return math.ceil(target_count * 1.3)

# Forbidden URL patterns (V4)
REJECT_PATTERNS = [
    r'namu\.wiki',
    r'google\.com/search',
    r'google\.com/url\?',
    r'youtube\.com',
    r'^https?://[^/]+/?$',  # domain root only
    r'/search\?',
    r'\.(pdf|zip|jpg|png)$',
]

# Source Media to Domain mapping dictionary (V3)
SOURCE_DOMAIN_MAP = {
    "zdnet": ["zdnet.co.kr"],
    "zdnet korea": ["zdnet.co.kr"],
    "전자신문": ["etnews.com"],
    "etnews": ["etnews.com"],
    "디지털데일리": ["ddaily.co.kr"],
    "ddaily": ["ddaily.co.kr"],
    "ai타임스": ["aitimes.com"],
    "aitimes": ["aitimes.com"],
    "techcrunch": ["techcrunch.com"],
    "venturebeat": ["venturebeat.com"],
    "the verge": ["theverge.com"],
    "wired": ["wired.com"],
    "ars technica": ["arstechnica.com"],
    "reuters": ["reuters.com"],
    "forbes": ["forbes.com"],
    "naver": ["naver.com", "news.naver.com"],
    "네이버": ["naver.com", "news.naver.com"],
}

# Track last request timestamp per domain for rate limiting
_last_request_time: Dict[str, float] = {}


def normalize_canonical_url(url: str, html_content: Optional[str] = None) -> str:
    """
    V7 Canonical URL normalization rule:
    - Use <link rel="canonical"> if present in HTML
    - Remove tracking params (utm_*, fbclid, gclid)
    - Remove trailing slashes, enforce https
    """
    canonical_target = url
    if html_content:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            link_tag = soup.find("link", rel=lambda r: r and "canonical" in r.lower() if isinstance(r, str) else False)
            if link_tag and link_tag.get("href"):
                href = link_tag["href"].strip()
                if href.startswith("http"):
                    canonical_target = href
        except Exception:
            pass

    parsed = urllib.parse.urlparse(canonical_target)
    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)

    # Filter out tracking query parameters
    cleaned_params = {
        k: v for k, v in query_params.items()
        if not (k.startswith("utm_") or k in ["fbclid", "gclid", "ref", "_hsenc", "_hsmi"])
    }

    new_query = urllib.parse.urlencode(cleaned_params, doseq=True)
    scheme = "https" if parsed.scheme in ["http", "https"] else parsed.scheme
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    return urllib.parse.urlunparse((scheme, netloc, path, parsed.params, new_query, parsed.fragment))


def _rate_limit_domain(domain: str, min_delay: float = 1.5):
    """Enforce minimum delay between requests to the same domain."""
    now = time.time()
    last_time = _last_request_time.get(domain, 0.0)
    elapsed = now - last_time
    if elapsed < min_delay:
        time.sleep(min_delay - elapsed)
    _last_request_time[domain] = time.time()


def load_allowed_domains() -> Set[str]:
    """Load whitelist domains from data/domain_config.json."""
    allowed = set()
    try:
        with open("data/domain_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            for key in ["vendor_domains", "partner_domains", "news_domains"]:
                raw_str = cfg.get(key, "")
                for item in raw_str.split(","):
                    item = item.strip()
                    if item:
                        # Extract domain part if full URL is given
                        if item.startswith("http"):
                            item = urllib.parse.urlparse(item).netloc
                        allowed.add(item.lower())
    except Exception as e:
        logger.warning(f"Could not load domain_config.json: {e}")
        # Fallback default domains
        allowed = {
            "zdnet.co.kr", "etnews.com", "aitimes.com", "ddaily.co.kr",
            "techcrunch.com", "venturebeat.com", "theverge.com", "wired.com",
            "arstechnica.com", "forbes.com", "reuters.com", "naver.com", "news.naver.com"
        }
    return allowed


def extract_published_date(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
    """
    V5 HTML Published Date extraction order:
    1) <meta property="article:published_time">
    2) JSON-LD script datePublished
    3) <meta property="og:published_time">
    4) <meta name="date"> or <time datetime="">
    Returns (pub_date_str_YYYY-MM-DD, source_type)
    """
    # 1. meta article:published_time
    tag = soup.find("meta", property="article:published_time")
    if tag and tag.get("content"):
        d = parse_date_string(tag["content"])
        if d:
            return d, "meta_article"

    # 2. JSON-LD datePublished
    for script in soup.find_all("script", type="application/ld+json"):
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}
                if isinstance(data, dict):
                    pub = data.get("datePublished") or data.get("dateCreated")
                    if pub:
                        d = parse_date_string(str(pub))
                        if d:
                            return d, "json_ld"
            except Exception:
                pass

    # 3. meta og:published_time
    tag = soup.find("meta", property="og:published_time")
    if tag and tag.get("content"):
        d = parse_date_string(tag["content"])
        if d:
            return d, "meta_og"

    # 4. meta name=date / time datetime
    tag = soup.find("meta", attrs={"name": re.compile(r"^date$", re.I)})
    if tag and tag.get("content"):
        d = parse_date_string(tag["content"])
        if d:
            return d, "meta_date"

    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        d = parse_date_string(time_tag["datetime"])
        if d:
            return d, "time_tag"

    return None, None


def parse_date_string(date_str: str) -> Optional[str]:
    """Parse various ISO/date string formats into YYYY-MM-DD string."""
    date_str = date_str.strip()
    match = re.search(r'(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})', date_str)
    if match:
        year, month, day = match.groups()
        try:
            d = date(int(year), int(month), int(day))
            return d.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def validate_article(
    url: str,
    source_media: str,
    cutoff_date: Optional[date] = None,
    existing_urls: Optional[Set[str]] = None,
    allowed_domains: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """
    Main article validator function for Phase 2.
    Checks V1 through V7 in sequence.
    """
    if existing_urls is None:
        existing_urls = set()
    if allowed_domains is None:
        allowed_domains = load_allowed_domains()

    result = {
        "passed": False,
        "reason": "",
        "final_url": url,
        "published_at": None,
        "date_source": None,
        "http_status": 0
    }

    # V4. Forbidden URL Pattern Check (early filter before network call)
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            result["reason"] = "INVALID_URL_PATTERN"
            return result

    # Domain parsing
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()

    # V2. Domain Whitelist Check
    domain_matched = any(domain == ad or domain.endswith("." + ad) for ad in allowed_domains)
    if not domain_matched:
        result["reason"] = "DOMAIN_NOT_ALLOWED"
        return result

    # V3. Source Media to Domain match check
    if source_media:
        s_media_lower = source_media.strip().lower()
        matched_expected = False
        for key, expected_domains in SOURCE_DOMAIN_MAP.items():
            if key in s_media_lower:
                matched_expected = True
                if not any(domain == ed or domain.endswith("." + ed) for ed in expected_domains):
                    result["reason"] = "SOURCE_MISMATCH"
                    return result
                break

    # V1. HTTP 200 OK Check & Rate limiting
    _rate_limit_domain(domain, min_delay=1.5)

    try:
        res = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=10)
        result["http_status"] = res.status_code
        result["final_url"] = res.url

        if res.status_code != 200:
            result["reason"] = f"HTTP_{res.status_code}"
            return result
    except Exception as e:
        logger.warning(f"HTTP request failed for {url}: {e}")
        result["reason"] = "HTTP_FAILED"
        return result

    # V4 Re-check on final_url in case redirect landed on forbidden pattern
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, result["final_url"], re.IGNORECASE):
            result["reason"] = "INVALID_URL_PATTERN"
            return result

    # Parse HTML for V5 & V7
    soup = BeautifulSoup(res.text, "html.parser")

    # V5. Published Date Extraction
    pub_date, date_src = extract_published_date(soup)
    result["published_at"] = pub_date
    result["date_source"] = date_src

    if not pub_date:
        result["reason"] = "NO_PUBLISH_DATE"
        return result

    # V6. Cutoff Date Check
    if cutoff_date:
        try:
            pub_d = datetime.strptime(pub_date, "%Y-%m-%d").date()
            if pub_d < cutoff_date:
                result["reason"] = "TOO_OLD"
                return result
        except ValueError:
            pass

    # V7. Canonical URL & Duplicate Check
    canonical = normalize_canonical_url(result["final_url"], html_content=res.text)
    result["final_url"] = canonical

    if canonical.lower() in existing_urls or url.lower() in existing_urls:
        result["reason"] = "DUPLICATE"
        return result

    # All checks passed!
    result["passed"] = True
    result["reason"] = "OK"
    return result


def sanitize_value_for_sheets(val: Any) -> Any:
    """
    Prevents CSV / Google Sheets Formula Injection.
    Prepends a single quote "'" to string values starting with '=', '+', '-', or '@'.
    Handles lists by converting them to '|' joined strings first or sanitizing elements.
    """
    if isinstance(val, list):
        joined_str = " | ".join([str(item).strip() for item in val if item is not None])
        return sanitize_value_for_sheets(joined_str)
        
    if isinstance(val, str):
        val_str = val.strip()
        if val_str and val_str[0] in ('=', '+', '-', '@'):
            return f"'{val_str}"
        return val_str
        
    if val is None:
        return ""
        
    return val


def validate_url(url: str) -> bool:
    """
    Checks if a URL is valid using validators module or urllib fallback.
    """
    if not url or not isinstance(url, str):
        return False
    url_str = url.strip()
    try:
        import validators
        if validators.url(url_str):
            return True
    except Exception:
        pass
        
    parsed = urllib.parse.urlparse(url_str if url_str.startswith(("http://", "https://")) else "https://" + url_str)
    return bool(parsed.scheme in ("http", "https") and parsed.netloc and "." in parsed.netloc)


def validate_candidate(candidate: dict, min_confidence: int = 70) -> dict:
    """
    Validates a single AI Vendor candidate.
    Returns a dict containing:
        - "is_valid": bool
        - "errors": list of error message strings
        - "sanitized_data": dict of sanitized/formatted candidate data
    """
    errors = []
    sanitized = {}
    
    # 1. Company Name (Required)
    name = candidate.get("company_name", "")
    if isinstance(name, str):
        name = name.strip()
    else:
        name = str(name).strip() if name else ""
    if not name:
        errors.append("Company Name is required.")
    sanitized["company_name"] = sanitize_value_for_sheets(name)
    
    # 2. Official Website (Required & Valid URL)
    website = candidate.get("official_website", "")
    if isinstance(website, str):
        website = website.strip()
    else:
        website = str(website).strip() if website else ""
    if not website:
        errors.append("Official Website is required.")
    elif not validate_url(website):
        errors.append(f"Invalid Official Website URL: {website}")
    sanitized["official_website"] = website
    
    # 3. Normalized Domain (Auto-generated/verified)
    normalized = normalize_domain(website) if website else ""
    if not normalized:
        errors.append("Failed to generate normalized domain.")
    sanitized["normalized_domain"] = normalized
    
    # 4. Primary AI Category
    category = candidate.get("primary_ai_category", "")
    if isinstance(category, str):
        category = category.strip()
    else:
        category = str(category).strip() if category else ""
    if not category:
        errors.append("Primary AI Category is required.")
    sanitized["primary_ai_category"] = category
    
    # 5. Confidence Score (Must be >= min_confidence)
    try:
        score = int(candidate.get("confidence_score", 0))
    except (ValueError, TypeError):
        score = 0
    if score < min_confidence:
        errors.append(f"Confidence score {score} is below the minimum threshold ({min_confidence}).")
    sanitized["confidence_score"] = score
    
    # 6. Recommendation Check
    rec = candidate.get("aika_recommendation", "")
    if isinstance(rec, str):
        rec = rec.strip()
    else:
        rec = str(rec).strip() if rec else ""
    if rec not in ("Strong Candidate", "Candidate", "Strong Partner", "Partner"):
        if not rec:
            rec = "Candidate"
        else:
            errors.append(f"Recommendation status '{rec}' is not acceptable for sheet storage.")
    sanitized["aika_recommendation"] = rec
    
    # 7. URL checks for evidence
    evidence = candidate.get("primary_evidence_url", "")
    if isinstance(evidence, str):
        evidence = evidence.strip()
    else:
        evidence = str(evidence).strip() if evidence else ""
    if evidence and not validate_url(evidence):
        errors.append(f"Invalid Primary Evidence URL: {evidence}")
    sanitized["primary_evidence_url"] = evidence
    
    # Sanitize remaining string / list fields
    sanitized["headquarters_country"] = sanitize_value_for_sheets(candidate.get("headquarters_country", ""))
    sanitized["main_ai_product"] = sanitize_value_for_sheets(candidate.get("main_ai_product", ""))
    sanitized["secondary_ai_categories"] = sanitize_value_for_sheets(candidate.get("secondary_ai_categories", []))
    sanitized["company_summary"] = sanitize_value_for_sheets(candidate.get("company_summary", ""))
    sanitized["target_customers"] = sanitize_value_for_sheets(candidate.get("target_customers", []))
    sanitized["target_industries"] = sanitize_value_for_sheets(candidate.get("target_industries", []))
    sanitized["main_use_cases"] = sanitize_value_for_sheets(candidate.get("main_use_cases", []))
    sanitized["deployment_type"] = sanitize_value_for_sheets(candidate.get("deployment_type", []))
    
    sanitized["official_product_page"] = str(candidate.get("official_product_page", "") or "").strip()
    sanitized["official_about_page"] = str(candidate.get("official_about_page", "") or "").strip()
    sanitized["official_contact_page"] = str(candidate.get("official_contact_page", "") or "").strip()
    
    sanitized["korea_presence_found"] = sanitize_value_for_sheets(candidate.get("korea_presence_found", "No evidence found"))
    sanitized["potential_korean_partner_type"] = sanitize_value_for_sheets(candidate.get("potential_korean_partner_type", []))
    sanitized["korea_market_relevance"] = sanitize_value_for_sheets(candidate.get("korea_market_relevance", ""))
    
    sanitized["b2b_product_confirmed"] = sanitize_value_for_sheets(candidate.get("b2b_product_confirmed", "Not publicly confirmed"))
    sanitized["proprietary_product_confirmed"] = sanitize_value_for_sheets(candidate.get("proprietary_product_confirmed", "Not publicly confirmed"))
    
    sanitized["additional_source_urls"] = sanitize_value_for_sheets(candidate.get("additional_source_urls", []))
    sanitized["review_status"] = str(candidate.get("review_status", "New") or "New").strip()
    sanitized["processing_status"] = str(candidate.get("processing_status", "Completed") or "Completed").strip()
    sanitized["research_notes"] = sanitize_value_for_sheets(candidate.get("research_notes", ""))
    sanitized["batch_id"] = str(candidate.get("batch_id", "") or "").strip()
    sanitized["research_date"] = str(candidate.get("research_date", "") or "").strip()
    
    # Verify optional pages if present
    for page_key in ("official_product_page", "official_about_page", "official_contact_page"):
        page_val = sanitized.get(page_key, "")
        if page_val and not validate_url(page_val):
            errors.append(f"Invalid URL for {page_key}: {page_val}")
            
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "sanitized_data": sanitized
    }

