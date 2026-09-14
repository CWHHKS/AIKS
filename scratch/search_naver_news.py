import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import re

query = "삼성SDS 생성형 AI 서비스 패브릭스 브리티"
url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

try:
    resp = urllib.request.urlopen(req)
    html = resp.read().decode('utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.text.strip()
        if 'news.naver.com' in href or 'etnews.com' in href or 'zdnet.co.kr' in href:
            if len(text) > 10:
                print(href, "-->", text[:50])
except Exception as e:
    print("Naver news search failed:", e)
