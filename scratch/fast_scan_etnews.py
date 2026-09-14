import requests
import concurrent.futures
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def check_url(url):
    try:
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            text = resp.text
            if "삼성SDS" in text and ("패브릭스" in text or "브리티" in text or "생성형 AI" in text or "생성형AI" in text):
                m = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
                title = m.group(1).strip() if m else "No Title"
                return (url, title)
    except Exception:
        pass
    return None

urls = []
for date in ["20240502", "20240503", "20240501"]:
    for i in range(1, 300):
        urls.append(f"https://www.etnews.com/{date}{i:06d}")

print(f"Scanning {len(urls)} URLs concurrently...", flush=True)

matches = []
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    results = executor.map(check_url, urls)
    for r in results:
        if r:
            print(f"MATCH: {r[0]} | {r[1]}", flush=True)
            matches.append(r)

print(f"Done. Total matches: {len(matches)}")
