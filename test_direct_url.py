import requests
import urllib.parse
import re

def search_google_direct_links(query):
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        # Find href="/url?q=..." or raw links
        raw_matches = re.findall(r'href="/url\?q=(https?://[^&"]+)', r.text)
        if not raw_matches:
            raw_matches = re.findall(r'href="(https?://[^"]+)"', r.text)
        
        filtered = []
        for link in raw_matches:
            link = urllib.parse.unquote(link)
            if not any(x in link.lower() for x in ['google.com', 'youtube.com', 'google.co.kr', 'schema.org', 'w3.org', 'gstatic.com']):
                filtered.append(link)
        return filtered
    except Exception as e:
        print("Error:", e)
        return []

if __name__ == "__main__":
    links1 = search_google_direct_links("OpenAI launches ChatGPT search TechCrunch")
    print("Google Search direct links 1:", links1[:3])

    links2 = search_google_direct_links("LG AI연구원 엑사원 3.0 오픈소스 공개 ZDNet Korea")
    print("Google Search direct links 2:", links2[:3])
