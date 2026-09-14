import requests
import urllib.parse
from duckduckgo_search import DDGS

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def is_url_valid(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    if url.lower() in ["none", "#", "null"]:
        return False
    try:
        resp = requests.get(url, headers=headers, timeout=4, allow_redirects=True, stream=True)
        all_urls = [resp.url.lower()] + [h.url.lower() for h in resp.history]
        for u in all_urls:
            if "/error" in u or "404" in u or "notfound" in u:
                return False
        if resp.status_code == 200:
            return True
    except Exception:
        pass
    return False

def get_direct_deep_link(title: str, media: str) -> str:
    query = f"{title} {media}".strip()
    try:
        ddg = DDGS()
        results = list(ddg.text(query, max_results=8))
        for res in results:
            href = res.get("href", "")
            if href and is_url_valid(href):
                return href
    except Exception as e:
        print("DDGS search exception:", e)

    return f"https://www.google.com/search?q={urllib.parse.quote(query)}"

if __name__ == "__main__":
    url1 = get_direct_deep_link("OpenAI launches ChatGPT search", "TechCrunch")
    print("Direct Deep Link 1:", url1)

    url2 = get_direct_deep_link("LG AI연구원 엑사원 3.0 오픈소스 공개", "ZDNet Korea")
    print("Direct Deep Link 2:", url2)
