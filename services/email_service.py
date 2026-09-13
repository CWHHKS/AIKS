import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "465"))
        self.sender_email = os.getenv("EMAIL_SENDER", "")
        self.sender_password = os.getenv("EMAIL_PASSWORD", "")
        self.default_receiver = os.getenv("EMAIL_RECEIVER", "changwan.lim@agichang.ai")

    def is_configured(self) -> bool:
        return bool(self.sender_email and self.sender_password)

    def render_news_card_html(self, article: Dict[str, Any], badge_color: str = "#2563eb") -> str:
        """Renders an individual news article as a stylish HTML card."""
        title = article.get("korean_title") or article.get("title", "제목 없음")
        orig_title = article.get("title", "")
        media = article.get("source_media", "출처 미상")
        pub_date = article.get("published_date", "")
        url = article.get("source_url", "#")
        category = article.get("primary_ai_category", "AI 일반")
        topic = article.get("news_topic", "")
        summary = article.get("korean_summary", "")
        detailed = article.get("detailed_summary", "")
        keywords = article.get("key_keywords", "")
        relevance = article.get("korea_market_relevance", "Medium")

        relevance_badge = ""
        if relevance == "High":
            relevance_badge = '<span style="background-color: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-left: 6px;">국내 영향도: 높음 🔥</span>'
        elif relevance == "Medium":
            relevance_badge = '<span style="background-color: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-left: 6px;">국내 영향도: 보통</span>'

        detailed_html = ""
        if detailed:
            items = []
            if isinstance(detailed, list):
                items = detailed
            elif isinstance(detailed, str):
                items = [line.strip().lstrip("•-1234567890. ") for line in detailed.split("\n") if line.strip()]
            
            if items:
                detailed_html = "<ul style='margin: 8px 0 0 0; padding-left: 20px; font-size: 13px; color: #475569; line-height: 1.6;'>"
                for it in items[:6]:
                    detailed_html += f"<li style='margin-bottom: 4px;'>{it}</li>"
                detailed_html += "</ul>"

        orig_title_html = ""
        if orig_title and orig_title != title:
            orig_title_html = f"<div style='font-size: 12px; color: #64748b; margin-top: 2px; font-style: italic;'>{orig_title}</div>"

        keywords_html = ""
        if keywords:
            keywords_html = f"<div style='margin-top: 8px; font-size: 11px; color: #64748b;'>🏷️ <b>키워드:</b> {keywords}</div>"

        # URL & Search fallback handling
        import urllib.parse
        search_query = f"{orig_title or title} {media}"
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
        
        raw_url = str(url or "").strip()
        is_generic_domain = False
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            try:
                parsed = urllib.parse.urlparse(raw_url)
                if not parsed.path or parsed.path in ["", "/"]:
                    is_generic_domain = True
            except Exception:
                is_generic_domain = True
        else:
            is_generic_domain = True

        target_url = google_search_url if (is_generic_domain or not raw_url or raw_url == "#") else raw_url

        return f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 18px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="display: flex; align-items: center; margin-bottom: 8px; flex-wrap: wrap;">
                <span style="background-color: {badge_color}; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">{category}</span>
                {f'<span style="background-color: #f1f5f9; color: #475569; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 6px;">{topic}</span>' if topic else ''}
                {relevance_badge}
                <span style="margin-left: auto; font-size: 12px; color: #94a3b8; font-weight: 500;">{media} • {pub_date}</span>
            </div>
            
            <a href="{target_url}" target="_blank" style="text-decoration: none; color: #0f172a; font-size: 16px; font-weight: 700; line-height: 1.4; display: block;">
                {title}
            </a>
            {orig_title_html}
            
            <div style="background-color: #f8fafc; border-left: 3px solid {badge_color}; padding: 10px 12px; border-radius: 0 6px 6px 0; margin-top: 10px; font-size: 13.5px; color: #334155; line-height: 1.55; font-weight: 500;">
                💡 {summary}
            </div>

            {detailed_html}
            {keywords_html}

            <div style="margin-top: 12px; display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
                <a href="{google_search_url}" target="_blank" style="display: inline-block; background-color: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; padding: 5px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 500; text-decoration: none;">
                    🔍 포털 검색
                </a>
                <a href="{target_url}" target="_blank" style="display: inline-block; background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; text-decoration: none;">
                    원문 기사 보기 →
                </a>
            </div>
        </div>
        """

    def build_daily_digest_html(
        self,
        morning_news: List[Dict[str, Any]],
        evening_news: List[Dict[str, Any]],
        report_date: Optional[str] = None
    ) -> str:
        """Builds the complete daily digest newsletter HTML."""
        if not report_date:
            report_date = datetime.now().strftime("%Y년 %m월 %d일")

        total_count = len(morning_news) + len(evening_news)

        morning_cards = "".join([self.render_news_card_html(a, badge_color="#0284c7") for a in morning_news]) if morning_news else "<p style='color: #64748b; font-size: 13px;'>새로 수집된 오전 뉴스가 없습니다.</p>"
        evening_cards = "".join([self.render_news_card_html(a, badge_color="#4f46e5") for a in evening_news]) if evening_news else "<p style='color: #64748b; font-size: 13px;'>전일 수집된 저녁 뉴스가 없습니다.</p>"

        html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIKA Daily AI News Briefing</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f1f5f9; padding: 24px 12px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 680px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 30px 24px; color: #ffffff; text-align: left;">
                            <div style="font-size: 13px; font-weight: 600; color: #38bdf8; letter-spacing: 1px; text-transform: uppercase;">AIKA Global Intelligence</div>
                            <h1 style="margin: 8px 0 4px 0; font-size: 22px; font-weight: 800; color: #ffffff;">⚡ AI 데일리 종합 뉴스 브리핑</h1>
                            <div style="font-size: 13px; color: #94a3b8;">{report_date} 기준 • 총 <b>{total_count}건</b>의 주요 AI 트렌드 리포트</div>
                        </td>
                    </tr>

                    <!-- Section: Morning 06:00 Updates -->
                    <tr>
                        <td style="padding: 24px 20px 8px 20px;">
                            <div style="border-bottom: 2px solid #0284c7; padding-bottom: 6px; margin-bottom: 16px;">
                                <h2 style="margin: 0; font-size: 17px; font-weight: 700; color: #0284c7;">
                                    🌅 오늘 아침 주요 AI 동향 (06:00 업데이트)
                                    <span style="font-size: 12px; background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 12px; margin-left: 8px; font-weight: 600;">{len(morning_news)}건</span>
                                </h2>
                            </div>
                            {morning_cards}
                        </td>
                    </tr>

                    <!-- Section: Previous Evening 18:00 Updates -->
                    <tr>
                        <td style="padding: 12px 20px 24px 20px;">
                            <div style="border-bottom: 2px solid #4f46e5; padding-bottom: 6px; margin-bottom: 16px;">
                                <h2 style="margin: 0; font-size: 17px; font-weight: 700; color: #4f46e5;">
                                    🌇 전일 저녁 주요 AI 동향 (18:00 업데이트)
                                    <span style="font-size: 12px; background: #ede9fe; color: #5b21b6; padding: 2px 8px; border-radius: 12px; margin-left: 8px; font-weight: 600;">{len(evening_news)}건</span>
                                </h2>
                            </div>
                            {evening_cards}
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 24px; text-align: center; color: #64748b; font-size: 12px; line-height: 1.5;">
                            <div>본 메일은 <b>AIKA Vendor & News Automated Discovery System</b>에서 자동 생성 및 발송되었습니다.</div>
                            <div style="margin-top: 4px; color: #94a3b8;">수신 계정: <b>changwan.lim@agichang.ai</b></div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
        return html_content

    def send_email(
        self,
        subject: str,
        html_body: str,
        to_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sends an email using configured SMTP credentials."""
        recipient = to_email or self.default_receiver
        if not self.sender_email or not self.sender_password:
            error_msg = "SMTP sender email or password is not configured in environment."
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"AIKA News Bot <{self.sender_email}>"
            msg["To"] = recipient

            # Attach HTML part
            html_part = MIMEText(html_body, "html", "utf-8")
            msg.attach(html_part)

            if self.smtp_port == 465:
                # SSL Connection
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, [recipient], msg.as_string())
            else:
                # TLS Connection (port 587)
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, [recipient], msg.as_string())

            logger.info(f"Successfully sent daily digest email to {recipient}")
            return {"success": True, "recipient": recipient}

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}
