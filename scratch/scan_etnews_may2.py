import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

found = []
print("Scanning ETNews article IDs for 2024-05-02...", flush=True)

for id_num in range(1, 300):
    url = f"https://www.etnews.com/20240502{id_num:06d}"
    try:
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            text = resp.text
            if "삼성SDS" in text or "패브릭스" in text:
                print(f"MATCH FOUND: {url}", flush=True)
                # extract title tag
                m = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
                title = m.group(1).strip() if m else "No Title"
                print(f"  Title: {title[:80]}", flush=True)
                found.append((url, title))
    except Exception:
        pass

print(f"\nTotal matches found: {len(found)}")
