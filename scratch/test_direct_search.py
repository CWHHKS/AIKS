import urllib.parse
import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def get_direct_urls(query):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    resp = requests.get(url, headers=HEADERS, timeout=6)
    found = []
    if resp.status_code == 200:
        links = re.findall(r'href=["\'](/l/\?uddg=[^"\']+|https?://[^"\']+)["\']', resp.text)
        for l in links:
            if "/l/?uddg=" in l or "uddg=" in l:
                full_l = "https://html.duckduckgo.com" + l if l.startswith("/") else l
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(full_l).query)
                if "uddg" in qs:
                    target = qs["uddg"][0]
                    if not any(x in target for x in ["duckduckgo.com", "google.com", "bing.com"]):
                        found.append(target)
    return found

if __name__ == "__main__":
    results = get_direct_urls("Palo Alto Networks Prisma AIRS launch news TechCrunch")
    for r in results[:5]:
        print("Direct Site URL:", r)
