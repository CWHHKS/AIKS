import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

query = "삼성SDS 패브릭스"
url = f"https://search.etnews.com/etnews/search.html?kwd={urllib.parse.quote(query)}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

try:
    resp = urllib.request.urlopen(req)
    html = resp.read().decode('utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if 'etnews.com/2024' in href or 'article' in href:
            print(href, a.text.strip())
except Exception as e:
    print("ETNews search failed:", e)
