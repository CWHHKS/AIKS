import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import sys

# Search naver news specifically on May 2, 2024
query = "삼성SDS 패브릭스 출시"
url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(query)}&ds=2024.05.01&de=2024.05.05"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

try:
    resp = urllib.request.urlopen(req)
    html = resp.read().decode('utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    news_items = soup.select('ul.list_news > li')
    print(f"Found {len(news_items)} news items")
    for item in news_items:
        title_tag = item.select_one('a.news_tit')
        press_tag = item.select_one('a.info.press')
        navers = item.select('a.info')
        if title_tag:
            title = title_tag.text.strip()
            link = title_tag.get('href')
            press = press_tag.text.strip() if press_tag else ""
            print(f"[{press}] {title}")
            print(f"  Direct Link: {link}")
            for n in navers:
                if 'news.naver.com' in n.get('href', ''):
                    print(f"  Naver Link: {n.get('href')}")
            print("-" * 50)
except Exception as e:
    print("Naver search failed:", e)
