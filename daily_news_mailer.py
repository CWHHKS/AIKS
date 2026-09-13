import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load environment variables if .env exists
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

from services.gemini_client import GeminiClient
from services.sheets_client import SheetsClient
from services.batch_service import BatchService, CATEGORY_CODES
from services.email_service import EmailService

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DailyNewsMailer")

BUFFER_FILE = os.path.join(BASE_DIR, "data", "news_daily_buffer.json")


def load_buffer() -> Dict[str, Any]:
    if os.path.exists(BUFFER_FILE):
        try:
            with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read buffer: {e}")
    return {"evening_news": [], "evening_date": None, "morning_news": [], "morning_date": None}


def save_buffer(data: Dict[str, Any]):
    os.makedirs(os.path.dirname(BUFFER_FILE), exist_ok=True)
    with open(BUFFER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def collect_news(target_count: int = 5, time_label: str = "Evening") -> List[Dict[str, Any]]:
    """Runs Gemini Search Grounding to collect recent AI news."""
    logger.info(f"🔍 Collecting {target_count} AI news articles for [{time_label}]...")
    
    gemini = GeminiClient()
    sheets = SheetsClient()
    batch_service = BatchService()

    existing_urls = []
    if sheets.is_connected() and sheets.news_spreadsheet:
        existing_urls = sheets.get_existing_news_urls()

    batch_id = f"NEWS-AUTO-{datetime.now().strftime('%Y%m%d%H%M')}"
    batch_params = {
        "batch_id": batch_id,
        "primary_category": "All",
        "news_topic": "All",
        "language": "All (EN + KO)",
        "target_count": target_count,
        "research_date": datetime.now().strftime("%Y-%m-%d"),
        "preferred_sources": "zdnet.co.kr, etnews.com, techcrunch.com, theverge.com, venturebeat.com"
    }

    report = gemini.run_news_discovery_stage(batch_params, existing_urls)
    structured = gemini.run_news_structuring_stage(batch_id, report, target_count)
    raw_news = structured.get("candidates", [])

    valid = []
    for a in raw_news:
        url = a.get("source_url", "").strip().lower()
        if url and url in existing_urls:
            continue
        a["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        a["review_status"] = "Auto-Collected"
        a["batch_id"] = batch_id
        valid.append(a)

    logger.info(f"✅ Successfully collected {len(valid)} new articles.")

    # Save to Google Sheets if connected
    if valid and sheets.is_connected() and sheets.news_spreadsheet:
        res = sheets.append_news(valid)
        if res.get("success"):
            batch_info = {
                "batch_id": batch_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "region": "Global/Korea",
                "category": "All",
                "industries": f"Auto {time_label} Digest",
                "candidate_count": len(raw_news),
                "saved_count": len(valid),
                "status": f"Completed (Auto-{time_label})"
            }
            sheets.write_batch_log(batch_info)
            batch_service.save_local_backup(batch_id, {"batch_id": batch_id, "candidates": valid, "status": "Auto-Saved"})

    return valid


def action_collect_evening(target_count: int = 5):
    """18:00 KST: Collect evening news and save to buffer."""
    logger.info("🌆 [Evening 18:00 KST] Starting Evening News Collection...")
    articles = collect_news(target_count=target_count, time_label="Evening")
    
    buffer = load_buffer()
    buffer["evening_news"] = articles
    buffer["evening_date"] = datetime.now().strftime("%Y-%m-%d")
    save_buffer(buffer)
    logger.info(f"🌆 Evening news ({len(articles)} articles) saved to buffer.")


def action_collect_and_send(target_count: int = 5, recipient: str = "changwan.lim@agichang.ai"):
    """06:00 KST: Collect morning news, combine with evening news, and send digest email."""
    logger.info("🌅 [Morning 06:00 KST] Starting Morning News Collection & Email Dispatch...")
    morning_articles = collect_news(target_count=target_count, time_label="Morning")

    buffer = load_buffer()
    evening_articles = buffer.get("evening_news", [])
    
    # If buffer evening news is missing, try to fetch from local backup or recent history
    if not evening_articles:
        logger.info("⚠️ No buffered evening news found. Generating comprehensive briefing with morning articles.")

    logger.info(f"📧 Preparing Daily Digest Email (Morning: {len(morning_articles)} / Evening: {len(evening_articles)})...")
    
    email_svc = EmailService()
    report_date = datetime.now().strftime("%Y년 %m월 %d일")
    subject = f"[AIKA Daily] ⚡ {report_date} AI 데일리 종합 뉴스 브리핑"

    html_content = email_svc.build_daily_digest_html(
        morning_news=morning_articles,
        evening_news=evening_articles,
        report_date=report_date
    )

    send_res = email_svc.send_email(
        subject=subject,
        html_body=html_content,
        to_email=recipient
    )

    if send_res.get("success"):
        logger.info(f"🎉 Email successfully dispatched to {recipient}!")
        # Clear buffer after successful dispatch
        buffer["evening_news"] = []
        buffer["evening_date"] = None
        buffer["last_sent_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_buffer(buffer)
    else:
        logger.error(f"❌ Failed to send email: {send_res.get('error')}")


def action_test_send(recipient: str = "changwan.lim@agichang.ai"):
    """Sends a sample test email to verify SMTP and HTML formatting."""
    logger.info(f"🧪 Sending test AI news digest email to {recipient}...")
    sample_morning = [
        {
            "title": "OpenAI Unveils Next-Gen Frontier Model with Advanced Reasoning",
            "korean_title": "OpenAI, 차세대 고성능 추론 AI 모델 공개",
            "source_media": "TechCrunch",
            "source_url": "https://techcrunch.com",
            "published_date": datetime.now().strftime("%Y-%m-%d"),
            "primary_ai_category": "AI 모델/LLM",
            "news_topic": "신제품/서비스 출시",
            "korean_summary": "OpenAI가 복잡한 수학, 코딩, 과학적 추론 문제를 획기적인 정확도로 해결하는 차세대 프론티어 AI 모델을 공식 발표했습니다.",
            "detailed_summary": "• 대규모 다단계 추론 프로세스를 실시간으로 수행하도록 최적화\n• 이전 세대 모델 대비 환각 현상(Hallucination) 40% 감소\n• 엔터프라이즈 API 즉시 제공 및 국내 주요 IT 기업과의 파트너십 논의 진행",
            "key_keywords": "OpenAI, LLM, 추론 AI, 벤치마크 신기록",
            "korea_market_relevance": "High"
        }
    ]
    sample_evening = [
        {
            "title": "Government Announces National AI Infrastructure Investment Plan",
            "korean_title": "정부, 국가 AI 컴퓨팅 인프라 대규모 투자 계획 발표",
            "source_media": "ZDNet Korea",
            "source_url": "https://zdnet.co.kr",
            "published_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "primary_ai_category": "AI 인프라/하드웨어",
            "news_topic": "정부 정책/규제",
            "korean_summary": "정부가 국내 AI 스타트업과 연구기관을 위한 첨단 GPU 클러스터 및 데이터센터 인프라 확충 지원 방안을 확정했습니다.",
            "detailed_summary": "• 민관 합동으로 첨단 AI 가속기 클라우드 바우처 공급 확대\n• 국산 AI 반도체 실증 사업과의 연계 강화\n• 2027년까지 글로벌 3대 AI 강국 도약 목표",
            "key_keywords": "AI 인프라, GPU 클라우드, 과학기술정보통신부",
            "korea_market_relevance": "High"
        }
    ]

    email_svc = EmailService()
    subject = f"[AIKA TEST] ⚡ {datetime.now().strftime('%Y-%m-%d')} AI 종합 뉴스 브리핑 (발송 테스트)"
    html = email_svc.build_daily_digest_html(
        morning_news=sample_morning,
        evening_news=sample_evening,
        report_date=datetime.now().strftime("%Y년 %m월 %d일")
    )
    res = email_svc.send_email(subject=subject, html_body=html, to_email=recipient)
    print(res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIKA Daily News Mailer Automation")
    parser.add_argument(
        "--action",
        choices=["collect_evening", "collect_and_send", "test_send"],
        default="collect_and_send",
        help="Action to perform: collect_evening (18:00), collect_and_send (06:00), or test_send"
    )
    parser.add_argument("--count", type=int, default=5, help="Number of articles to collect per run")
    parser.add_argument("--to", type=str, default="changwan.lim@agichang.ai", help="Recipient email address")

    args = parser.parse_args()

    if args.action == "collect_evening":
        action_collect_evening(target_count=args.count)
    elif args.action == "collect_and_send":
        action_collect_and_send(target_count=args.count, recipient=args.to)
    elif args.action == "test_send":
        action_test_send(recipient=args.to)
