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
            if "삼성SDS" in text and ("패브릭스" in text or "브리티" in text):
                m = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
                title = m.group(1).strip() if m else "No Title"
                return (url, title)
    except Exception:
        pass
    return None

urls = []
# 030 = ETNews on Naver
for i in range(3202800, 3203200):
    urls.append(f"https://n.news.naver.com/mnews/article/030/{i:010d}")

# 092 = ZDNet Korea on Naver
for i in range(232980, 233050):
    urls.append(f"https://n.news.naver.com/mnews/article/092/{i:010d}")

print(f"Scanning {len(urls)} Naver article URLs...", flush=True)

matches = []
with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    results = executor.map(check_url, urls)
    for r in results:
        if r:
            print(f"MATCH: {r[0]} | {r[1]}", flush=True)
            matches.append(r)

print(f"Done. Total matches: {len(matches)}")
