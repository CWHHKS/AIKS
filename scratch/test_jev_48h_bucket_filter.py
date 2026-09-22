import sys
import os
from datetime import datetime, timedelta

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.typesafe_service import TypeSafeNewsClassifier
from services.gemini_client import GeminiClient

def test_jev_evaluation():
    print("=== 1. Jev TypeSafe Classifier Bucket & Recency Test ===")
    classifier = TypeSafeNewsClassifier()
    print(f"Jev Classifier Available: {classifier.is_available()}")

    # Test cases: title, summary
    test_articles = [
        {
            "title": "네이버클라우드, 기업용 AI 솔루션 '하이퍼클로바X 엔터프라이즈' 신규 출시",
            "text": "네이버클라우드가 국내 기업들을 위한 한국어 특화 생성형 AI 솔루션 하이퍼클로바X 엔터프라이즈를 공식 출시했다.",
            "expected_bucket": "국내 AI 솔루션"
        },
        {
            "title": "OpenAI, GPT-5 모델 정식 발표 및 API 출시",
            "text": "OpenAI가 차세대 멀티모달 프론티어 AI 모델 GPT-5를 전세계 개발자들에게 API 형태로 전격 공개했다.",
            "expected_bucket": "해외 AI 솔루션"
        },
        {
            "title": "과학기술정보통신부, 국내 AI 스타트업 육성 1조원 펀드 조성 발표",
            "text": "과기정통부가 국내 생태계 강화를 위해 AI 펀드를 1조원 규모로 확대 개편한다는 정책을 발표했다.",
            "expected_bucket": "국내 AI 소식"
        },
        {
            "title": "미국 정부, 글로벌 반도체 및 AI 칩 수출 규제안 가이드라인 개정",
            "text": "미국 백악관이 첨단 AI 칩에 대한 글로벌 가이드라인 규제안을 발표했다.",
            "expected_bucket": "해외 AI 소식"
        }
    ]

    for idx, item in enumerate(test_articles, 1):
        res = classifier.evaluate_article(item["title"], item["text"])
        print(f"\n[Test Article {idx}] {item['title']}")
        print(f"  - Target Bucket: {res.get('target_bucket')}")
        print(f"  - Region: {res.get('article_region')} | Type: {res.get('article_type')}")
        print(f"  - AI Prob: {res.get('ai_probability'):.2f} | Pass: {res.get('is_ai_news')}")

def test_48h_date_filter():
    print("\n=== 2. Python 48-Hour Date Filter Test ===")
    client = GeminiClient()
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    two_days_ago_str = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    four_days_ago_str = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
    last_year_str = "2024-05-10"

    print(f"Today ({today_str}): {client._is_within_48h(today_str)} (Expected: True)")
    print(f"Yesterday ({yesterday_str}): {client._is_within_48h(yesterday_str)} (Expected: True)")
    print(f"2 Days Ago ({two_days_ago_str}): {client._is_within_48h(two_days_ago_str)} (Expected: True)")
    print(f"4 Days Ago ({four_days_ago_str}): {client._is_within_48h(four_days_ago_str)} (Expected: False)")
    print(f"Last Year ({last_year_str}): {client._is_within_48h(last_year_str)} (Expected: False)")

if __name__ == "__main__":
    test_jev_evaluation()
    test_48h_date_filter()
