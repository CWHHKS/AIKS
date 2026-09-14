import re
import time
import json
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, Set
import urllib.parse
import requests
from bs4 import BeautifulSoup

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
