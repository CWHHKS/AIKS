import os
import re
import urllib.parse
import logging
import requests
import random
from typing import List, Dict, Any
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

logger = logging.getLogger(__name__)

HEADERS_SET = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9"
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"
    }
]

def clean_html_tags(text: str) -> str:
    """Removes HTML tags and cleans up entities in raw text."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&quot;", '"').replace("&amp;", '&').replace("&lt;", '<').replace("&gt;", '>').replace("&apos;", "'").replace("&nbsp;", ' ')
    return re.sub(r'\s+', ' ', text).strip()

def search_naver_news_api(query: str, display: int = 10) -> List[Dict[str, Any]]:
    """
    Queries Naver Open API (if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are configured).
    Returns list of candidate news dictionaries.
    """
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        return []

    url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(query)}&display={display}&sort=date"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            results = []
            for item in items:
                title = clean_html_tags(item.get("title", ""))
                desc = clean_html_tags(item.get("description", ""))
                origin_link = item.get("originallink", "")
                naver_link = item.get("link", "")

                ref_urls = []
                if naver_link and "news.naver.com" in naver_link:
                    ref_urls.append(naver_link)
                if origin_link and origin_link != naver_link:
                    ref_urls.append(origin_link)

                results.append({
                    "title": title,
                    "korean_title": title,
                    "summary": desc,
                    "source_media": "네이버뉴스",
                    "source_url": naver_link or origin_link,
                    "reference_urls": ref_urls
                })
            logger.info(f"Naver Open API returned {len(results)} items for query '{query}'")
            return results
    except Exception as e:
        logger.warning(f"Naver Open API search failed: {e}")
    return []

def search_naver_news_html(query: str, display: int = 10) -> List[Dict[str, Any]]:
    """
    Fallback HTML Scraper for Naver News real-time search.
    Does not require API keys and extracts Naver portal deep links (n.news.naver.com).
    """
    if not query:
        return []

    search_url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}&sort=1"
    headers = random.choice(HEADERS_SET)

    try:
        resp = requests.get(search_url, headers=headers, timeout=5)
        if resp.status_code != 200:
            logger.warning(f"Naver News HTML search returned HTTP {resp.status_code}")
            return []

        resp.encoding = 'utf-8'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        seen_urls = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'n.news.naver.com/mnews/article/' in href and href not in seen_urls:
                # Traverse 5-6 levels up to find the complete news card block
                card = a
                for _ in range(6):
                    if card.parent:
                        card = card.parent

                title_text = ""
                media_name = "네이버뉴스"
                summary_text = ""
                ref_urls = [href]

                if card:
                    for anc in card.find_all('a', href=True):
                        anc_href = anc['href']
                        txt = anc.get_text(strip=True)
                        txt_clean = txt.replace('네이버뉴스', '').replace('새 창 열림', '').replace('새창열림', '').replace('Keep으로 바로가기', '').strip()

                        if anc_href and anc_href.startswith("http") and anc_href not in ref_urls and "naver.com" not in anc_href:
                            ref_urls.append(anc_href)

                        if len(txt_clean) > 8 and not txt_clean.startswith("http") and not any(bad in txt_clean for bad in ['바로가기', '네이버뉴스', '보내기', '메인', '언론사']) and not title_text:
                            title_text = txt_clean
                        elif txt_clean and len(txt_clean) <= 15 and media_name == "네이버뉴스":
                            media_name = txt_clean

                    dsc_tag = card.find('div', class_=re.compile(r'dsc|desc|text|summary'))
                    if dsc_tag:
                        summary_text = dsc_tag.get_text(strip=True)

                if not title_text or "새 창 열림" in title_text:
                    continue

                seen_urls.add(href)
                results.append({
                    "title": title_text,
                    "korean_title": title_text,
                    "summary": summary_text or title_text,
                    "source_media": media_name or "네이버뉴스",
                    "source_url": href,
                    "reference_urls": ref_urls
                })

                if len(results) >= display:
                    break

        logger.info(f"Naver News HTML scraper returned {len(results)} items for query '{query}'")
        return results
    except Exception as e:
        logger.warning(f"Naver News HTML scraper failed: {e}")

    return []

def get_naver_news_candidates(query: str, display: int = 10) -> List[Dict[str, Any]]:
    """
    High-level entry point for Naver Real-Time News Search.
    Tries Naver Open API first, falls back to Naver News HTML search.
    """
    api_results = search_naver_news_api(query, display=display)
    if api_results:
        return api_results
    return search_naver_news_html(query, display=display)
