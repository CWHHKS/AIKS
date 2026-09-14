import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import requests
import urllib.parse
import re
from bs4 import BeautifulSoup
from services.audit_agent import GPTNewsAuditor

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

def resolve_via_naver_search(title: str, media: str = "") -> str:
    """Searches Naver News for stable portal deep-link when direct domain is WAF blocked."""
    query = title[:40]
    search_url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=5)
        if resp.status_code != 200:
            return ""
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        candidates = []
        for a in soup.find_all('a'):
            href = a.get('href', '')
            if 'n.news.naver.com/mnews/article/' in href and href not in candidates:
                candidates.append(href)
                
        # Media channel preference mapping
        media_lower = media.lower()
        pref_code = None
        if "전자신문" in media_lower or "etnews" in media_lower:
            pref_code = "/030/"
        elif "zdnet" in media_lower or "지디넷" in media_lower:
            pref_code = "/092/"
        elif "연합뉴스" in media_lower or "yna" in media_lower:
            pref_code = "/001/"
            
        if pref_code:
            pref_list = [c for c in candidates if pref_code in c]
            other_list = [c for c in candidates if pref_code not in c]
            candidates = pref_list + other_list
            
        auditor = GPTNewsAuditor()
        for cand in candidates:
            try:
                r = requests.get(cand, headers=HEADERS, timeout=5)
                if r.status_code == 200:
                    r.encoding = r.apparent_encoding or 'utf-8'
                    cleaned = re.sub(r'<script[^>]*>.*?</script>', ' ', r.text, flags=re.DOTALL | re.IGNORECASE)
                    cleaned = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned, flags=re.DOTALL | re.IGNORECASE)
                    clean_text = re.sub(r'<[^>]+>', ' ', cleaned)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    
                    audit_res = auditor.audit_news_page(title, media, clean_text)
                    if audit_res.get("approved"):
                        return cand
            except Exception:
                pass
    except Exception as e:
        print("Naver search exception:", e)
    return ""

# Test on Item 14 (ETNews WAF Blocked link)
title_14 = "국가AI위원회 출범... 'AI 3대 강국(G3)' 도약 선언"
media_14 = "전자신문"
res_14 = resolve_via_naver_search(title_14, media_14)
print("Resolved Item 14 via Naver Fallback:", res_14)

# Test on Item 12 (Samsung SDS FabriX)
title_12 = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media_12 = "전자신문"
res_12 = resolve_via_naver_search(title_12, media_12)
print("Resolved Item 12 via Naver Fallback:", res_12)
