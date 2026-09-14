import requests
from bs4 import BeautifulSoup
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

url = "https://search.naver.com/search.naver?where=news&query=%EC%82%BC%EC%84%B1SDS%20%ED%8C%A8%EB%B8%8C%EB%A6%AD%EC%8A%A4%20%EC%B6%9C%EC%8B%9C"
r = requests.get(url, headers=headers)
print("Naver search status code:", r.status_code, flush=True)

soup = BeautifulSoup(r.text, 'html.parser')
articles = []
for a in soup.select('a.news_tit'):
    link = a.get('href')
    title = a.text.strip()
    print(f"TITLE: {title}", flush=True)
    print(f"LINK: {link}", flush=True)
    articles.append((link, title))

print(f"Found {len(articles)} articles.", flush=True)
