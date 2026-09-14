import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

def make_clean_search_query(title: str, title_kr: str = "") -> str:
    """Cleans punctuation and selects best search query words for Naver / Web Search."""
    text = title_kr if title_kr else title
    # Remove parenthesized text or brackets
    text = re.sub(r'[\(\[\{].*?[\)\]\}]', ' ', text)
    # Keep only Korean, English, numbers, and spaces
    clean = re.sub(r'[^\w\s가-힣a-zA-Z0-9]', ' ', text)
    words = [w for w in clean.split() if len(w) >= 2]
    # Take first 5 meaningful words
    query = " ".join(words[:5])
    return query

test_titles = [
    ("OpenAI is reportedly preparing to launch an AI agent called 'Operator'", "오픈AI, 내년 1월 PC 제어하는 자율형 AI 에이전트 '오퍼레이터' 출시 전"),
    ("[TechCrunch] 디프시크 쇼크에 엔비디아 시총 700조 증발... AI 시장 요동", "디프시크 쇼크에 엔비디아 시총 700조 증발"),
    ("국가AI위원회 출범... 'AI 3대 강국(G3)' 도약 선언", "국가AI위원회 출범 AI 3대 강국 G3 도약 선언"),
    ("Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B", "세이프 슈퍼인텔리전스 10억 달러 투자 유치")
]

for t_en, t_kr in test_titles:
    q = make_clean_search_query(t_en, t_kr)
    print(f"Original: {t_en[:40]}... / {t_kr[:30]}...")
    print(f" -> Clean Query: '{q}'")
    
    url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(q)}"
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(r.text, 'html.parser')
    cands = [a.get('href') for a in soup.find_all('a') if 'n.news.naver.com/mnews/article/' in a.get('href', '')]
    print(f" -> Found {len(cands)} Naver candidates!\n")
