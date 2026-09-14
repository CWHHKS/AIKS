import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import sys

query = "삼성SDS 패브릭스"
url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'})

try:
    resp = urllib.request.urlopen(req)
    html = resp.read().decode('utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a'):
        href = a.get('href', '')
        title = a.text.strip()
        if 'etnews.com' in href or 'zdnet.co.kr' in href or 'chosun.com' in href or 'hankyung.com' in href or 'news.naver.com' in href:
            if '패브릭스' in title or 'SDS' in title or 'AI' in title or '출시' in title:
                print(f"[{title[:40]}] -> {href}")
except Exception as e:
    print("Search error:", e)
