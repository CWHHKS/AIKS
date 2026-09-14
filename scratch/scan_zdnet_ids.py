import requests
import concurrent.futures
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def check_zdnet(url):
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

# ZDNet Korea URL format: https://zdnet.co.kr/view/?no=20240502HHMMSS
# Let's generate sample timestamps throughout 20240502
urls = []
for hh in range(8, 20):
    for mm in range(0, 60, 2):
        for ss in range(0, 60, 15):
            urls.append(f"https://zdnet.co.kr/view/?no=20240502{hh:02d}{mm:02d}{ss:02d}")

print(f"Testing {len(urls)} ZDNet URLs...", flush=True)

matches = []
with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    results = executor.map(check_zdnet, urls)
    for r in results:
        if r:
            print(f"MATCH: {r[0]} | {r[1][:60]}", flush=True)
            matches.append(r)

print(f"Done. Found {len(matches)} matches.")
