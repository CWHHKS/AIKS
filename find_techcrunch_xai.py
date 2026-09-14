import requests
from duckduckgo_search import DDGS

ddg = DDGS()
headers = {'User-Agent': 'Mozilla/5.0'}

results = list(ddg.text("site:techcrunch.com xAI 6 billion", max_results=10))
print("Results count:", len(results))
for r in results:
    href = r.get("href", "")
    print("Href:", href)
    try:
        chk = requests.get(href, headers=headers, timeout=5, stream=True)
        print("Status:", chk.status_code, "Final URL:", chk.url)
    except Exception as e:
        print("Error:", e)
    print("-" * 50)
