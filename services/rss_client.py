import os
import re
import time
import logging
import urllib.parse
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("rss_client")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*"
}

DEFAULT_SOURCES = [
    {"name": "AI타임스", "url": "https://www.aitimes.com/rss/allArticle.xml"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
    {"name": "디지털데일리", "url": "https://www.ddaily.co.kr/rss/allArticle.xml"}
]


def load_sources_yaml() -> List[Dict[str, str]]:
    """Load sources from data/sources.yaml if available."""
    sources_path = os.path.join("data", "sources.yaml")
    if os.path.exists(sources_path):
        try:
            import yaml
            with open(sources_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict) and "rss_feeds" in data:
                    return data["rss_feeds"]
        except Exception as e:
            logger.warning(f"Could not load sources.yaml via PyYAML ({e}), using default list.")

    return DEFAULT_SOURCES


def resolve_redirect_url(url: str, timeout: int = 5) -> str:
    """Follow HTTP redirects (302/301) to get final direct article URL."""
    try:
        res = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=timeout)
        if res.status_code == 200 and res.url:
            return res.url
    except Exception as e:
        logger.warning(f"Failed redirect resolution for {url}: {e}")
    return url


def parse_pubdate_to_str(raw_date: str) -> Optional[str]:
    """Parse various RSS pubDate formats to YYYY-MM-DD string."""
    if not raw_date:
        return None
    raw_date = raw_date.strip()

    # Match YYYY-MM-DD
    m = re.search(r'(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})', raw_date)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Match RFC822 format (e.g. Mon, 14 Sep 2026 10:00:00 GMT)
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw_date)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


def fetch_google_news_rss(query: str, days: int = 7, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Channel A: Google News RSS with when:Nd parameter for date filtering.
    URL: https://news.google.com/rss/search?q={query}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko
    """
    encoded_query = urllib.parse.quote(f"{query} when:{days}d")
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

    logger.info(f"[RSS Channel A] Fetching Google News RSS: {rss_url}")
    results = []

    try:
        res = requests.get(rss_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            logger.warning(f"Google News RSS HTTP {res.status_code}")
            return results

        soup = BeautifulSoup(res.text, "xml" if "xml" in res.text[:100].lower() else "html.parser")
        items = soup.find_all("item")

        for item in items[:max_results]:
            title_tag = item.find("title")
            link_tag = item.find("link")
            pubdate_tag = item.find("pubDate") or item.find("pubdate")
            source_tag = item.find("source")

            title = title_tag.get_text(strip=True) if title_tag else ""
            raw_link = link_tag.get_text(strip=True) if link_tag else ""
            pub_raw = pubdate_tag.get_text(strip=True) if pubdate_tag else ""
            source_media = source_tag.get_text(strip=True) if source_tag else "Google News"

            # Resolve Google News redirect link to direct publisher URL
            final_url = resolve_redirect_url(raw_link) if raw_link else ""
            pub_date = parse_pubdate_to_str(pub_raw)

            if title and final_url:
                results.append({
                    "title": title,
                    "korean_title": title,
                    "source_url": final_url,
                    "source_media": source_media,
                    "published_date": pub_date or datetime.now().strftime("%Y-%m-%d"),
                    "discovery_channel": "google_news_rss",
                    "reference_urls": [final_url] if final_url else []
                })

    except Exception as e:
        logger.error(f"Error fetching Google News RSS: {e}")

    logger.info(f"[RSS Channel A] Found {len(results)} candidate items.")
    return results


def fetch_direct_media_rss(cutoff_date: Optional[date] = None, max_per_feed: int = 5) -> List[Dict[str, Any]]:
    """
    Channel B: Direct Media RSS feed parsing (ZDNet, ETNews, TechCrunch, etc.)
    Filters out articles published before cutoff_date at discovery stage.
    """
    sources = load_sources_yaml()
    results = []

    for src in sources:
        media_name = src.get("name", "RSS Media")
        feed_url = src.get("url", "")
        if not feed_url:
            continue

        try:
            logger.info(f"[RSS Channel B] Fetching RSS feed for {media_name}...")
            res = requests.get(feed_url, headers=HEADERS, timeout=8)
            if res.status_code != 200:
                logger.warning(f"RSS feed {media_name} returned HTTP {res.status_code}")
                continue

            soup = BeautifulSoup(res.text, "xml" if "xml" in res.text[:100].lower() else "html.parser")
            items = soup.find_all(["item", "entry"])

            count = 0
            for item in items:
                if count >= max_per_feed:
                    break

                title_tag = item.find(["title"])
                link_tag = item.find(["link"])
                pub_tag = item.find(["pubDate", "pubdate", "published", "updated"])
                desc_tag = item.find(["description", "summary", "content"])

                title = title_tag.get_text(strip=True) if title_tag else ""
                
                # Get link URL
                raw_link = ""
                if link_tag:
                    raw_link = link_tag.get("href") or link_tag.get_text(strip=True) or ""

                pub_raw = pub_tag.get_text(strip=True) if pub_tag else ""
                desc = desc_tag.get_text(strip=True) if desc_tag else ""

                pub_date = parse_pubdate_to_str(pub_raw)

                # Cutoff date check at discovery level
                if cutoff_date and pub_date:
                    try:
                        parsed_pub_d = datetime.strptime(pub_date, "%Y-%m-%d").date()
                        if parsed_pub_d < cutoff_date:
                            continue  # Skip old article
                    except ValueError:
                        pass

                if title and raw_link:
                    results.append({
                        "title": title,
                        "korean_title": title,
                        "source_url": raw_link,
                        "source_media": media_name,
                        "published_date": pub_date or datetime.now().strftime("%Y-%m-%d"),
                        "discovery_channel": "direct_rss",
                        "rss_description": desc[:500],
                        "reference_urls": [raw_link]
                    })
                    count += 1

        except Exception as e:
            logger.warning(f"[RSS Channel B] Failed fetching RSS for {media_name}: {e}")

    logger.info(f"[RSS Channel B] Total direct RSS candidates collected: {len(results)}")
    return results
