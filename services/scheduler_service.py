import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from services.gemini_client import GeminiClient
from services.sheets_client import SheetsClient
from services.batch_service import BatchService, CATEGORY_CODES

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.getcwd(), "data", "timer_config.json")

DEFAULT_CONFIG = {
    "vendor": {
        "enabled": False,
        "mode": "interval",  # "interval" or "daily"
        "interval_hours": 24,
        "daily_count": 1,
        "daily_times": "09:00",
        "daily_time": "09:00",
        "email_enabled": False,
        "recipient_email": "changwan.lim@agichang.ai",
        "email_send_mode": "immediate",
        "email_dispatch_time": "09:30",
        "target_count": 5,
        "category": "All",
        "region": "Global",
        "last_run": None,
        "last_status": "Idle"
    },
    "partner": {
        "enabled": False,
        "mode": "daily",
        "interval_hours": 24,
        "daily_count": 1,
        "daily_times": "09:00",
        "daily_time": "09:00",
        "email_enabled": False,
        "recipient_email": "changwan.lim@agichang.ai",
        "email_send_mode": "immediate",
        "email_dispatch_time": "09:30",
        "target_count": 5,
        "category": "All",
        "last_run": None,
        "last_status": "Idle"
    },
    "news": {
        "enabled": False,
        "mode": "interval",
        "interval_hours": 6,
        "daily_count": 1,
        "daily_times": "08:00",
        "daily_time": "08:00",
        "email_enabled": False,
        "recipient_email": "changwan.lim@agichang.ai",
        "email_send_mode": "immediate",
        "email_dispatch_time": "08:30, 18:30",
        "target_count": 5,
        "primary_category": "All",
        "news_topic": "All",
        "last_run": None,
        "last_status": "Idle"
    }
}

class SchedulerService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchedulerService, cls).__new__(cls)
            cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self.config = self._load_config()
        self.scheduler.start()
        logger.info("BackgroundScheduler started.")
        self._sync_jobs()

    def _load_config(self) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    # Merge with default config to ensure all keys exist
                    merged = DEFAULT_CONFIG.copy()
                    for k, v in cfg.items():
                        if k in merged:
                            merged[k].update(v)
                    return merged
            except Exception as e:
                logger.error(f"Error loading timer config: {e}")
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info("Saved timer_config.json")
            self._sync_jobs()
        except Exception as e:
            logger.error(f"Error saving timer config: {e}")

    def update_task_config(self, task_name: str, task_cfg: Dict[str, Any]):
        if task_name in self.config:
            self.config[task_name].update(task_cfg)
            self.save_config()

    def _sync_jobs(self):
        """Syncs APScheduler jobs with current config."""
        func_map = {
            "vendor": self._run_auto_vendor_job,
            "partner": self._run_auto_partner_job,
            "news": self._run_auto_news_job
        }

        for task_name in ["vendor", "partner", "news"]:
            # Remove all existing jobs for this task
            for job in list(self.scheduler.get_jobs()):
                if job.id.startswith(f"auto_{task_name}_job"):
                    self.scheduler.remove_job(job.id)

            task_cfg = self.config.get(task_name, {})

            if task_cfg.get("enabled", False):
                mode = task_cfg.get("mode", "interval")
                if mode == "interval":
                    hours = max(1, int(task_cfg.get("interval_hours", 24)))
                    trigger = IntervalTrigger(hours=hours)
                    self.scheduler.add_job(
                        func=func_map[task_name],
                        trigger=trigger,
                        id=f"auto_{task_name}_job",
                        replace_existing=True
                    )
                    logger.info(f"Scheduled job 'auto_{task_name}_job' with interval '{hours}h'")
                else:  # daily multi-time
                    times_raw = task_cfg.get("daily_times") or task_cfg.get("daily_time", "09:00")
                    time_list = [t.strip() for t in str(times_raw).split(",") if t.strip()]
                    if not time_list:
                        time_list = ["09:00"]
                    
                    for idx, t_str in enumerate(time_list):
                        try:
                            hh, mm = map(int, t_str.split(":"))
                        except Exception:
                            hh, mm = 9, 0
                        trigger = CronTrigger(hour=hh, minute=mm)
                        job_id = f"auto_{task_name}_job_{idx}"
                        self.scheduler.add_job(
                            func=func_map[task_name],
                            trigger=trigger,
                            id=job_id,
                            replace_existing=True
                        )
                        logger.info(f"Scheduled job '{job_id}' daily at {hh:02d}:{mm:02d}")

            # Sync Email Dispatch Job if email_enabled and email_send_mode == "scheduled"
            if task_cfg.get("enabled", False) and task_cfg.get("email_enabled", False) and task_cfg.get("email_send_mode") == "scheduled":
                times_raw = task_cfg.get("email_dispatch_time") or "08:30"
                time_list = [t.strip() for t in str(times_raw).split(",") if t.strip()]
                if not time_list:
                    time_list = ["08:30"]

                for idx, t_str in enumerate(time_list):
                    try:
                        hh, mm = map(int, t_str.split(":"))
                    except Exception:
                        hh, mm = 8, 30
                    trigger = CronTrigger(hour=hh, minute=mm)
                    email_job_id = f"auto_{task_name}_email_job_{idx}"
                    # Create job using default arg binding to prevent closure loop bug
                    self.scheduler.add_job(
                        func=self._make_email_runner(task_name),
                        trigger=trigger,
                        id=email_job_id,
                        replace_existing=True
                    )
                    logger.info(f"Scheduled email job '{email_job_id}' daily at {hh:02d}:{mm:02d}")

    # ═══════════════════════════════════════════════════════════════
    # AUTO RUNNERS FOR EACH SEARCH TOOL
    # ═══════════════════════════════════════════════════════════════

    def _run_auto_vendor_job(self):
        logger.info("⏰ [AUTO TIMER] Starting scheduled Vendor Discovery...")
        task_cfg = self.config.get("vendor", {})
        try:
            sheets = SheetsClient()
            gemini = GeminiClient()
            batch_service = BatchService()

            if not sheets.is_connected():
                logger.error("[AUTO VENDOR] Sheets is not connected.")
                return

            cat_code = CATEGORY_CODES.get(task_cfg.get("category", "All"), "ALL")
            batch_id = f"GV-{cat_code}-{datetime.now().strftime('%Y%m%d')}-AUTO"
            existing_domains = sheets.get_existing_domains()

            batch_params = {
                "batch_id": batch_id,
                "region": task_cfg.get("region", "Global"),
                "category": task_cfg.get("category", "All"),
                "industries": "General Enterprise",
                "minimum_confidence_score": 70,
                "exclude_hyperscalers": True,
                "target_count": task_cfg.get("target_count", 5),
                "research_date": datetime.now().strftime("%Y-%m-%d"),
                "preferred_sources": "ycombinator.com, crunchbase.com"
            }

            report = gemini.run_discovery_stage(batch_params, existing_domains)
            structured = gemini.run_structuring_stage(batch_id, report, task_cfg.get("target_count", 5))
            raw_cands = structured.get("candidates", [])

            valid = []
            for c in raw_cands:
                domain = c.get("normalized_domain", "").strip().lower()
                if domain in existing_domains:
                    continue
                c["review_status"] = "Auto-Collected"
                c["processing_status"] = "Completed"
                c["research_date"] = batch_params["research_date"]
                c["batch_id"] = batch_id
                valid.append(c)

            if valid:
                res = sheets.append_vendors(valid)
                if res.get("success"):
                    batch_info = {
                        "batch_id": batch_id,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "region": batch_params["region"],
                        "category": batch_params["category"],
                        "industries": batch_params["industries"],
                        "candidate_count": len(raw_cands),
                        "saved_count": len(valid),
                        "status": "Completed (Auto-Collected)"
                    }
                    sheets.write_batch_log(batch_info)
                    batch_service.save_local_backup(batch_id, {"batch_id": batch_id, "candidates": valid, "status": "Auto-Saved"})

            if valid and task_cfg.get("email_enabled", False):
                self._send_job_email_report("vendor", task_cfg, valid)

            self.config["vendor"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["vendor"]["last_status"] = f"Success ({len(valid)} saved)"
            self.save_config()
            logger.info(f"[AUTO VENDOR] Finished successfully. {len(valid)} saved.")

        except Exception as e:
            logger.error(f"[AUTO VENDOR] Failed: {e}")
            self.config["vendor"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["vendor"]["last_status"] = f"Failed: {e}"
            self.save_config()

    def _run_auto_partner_job(self):
        logger.info("⏰ [AUTO TIMER] Starting scheduled Partner Discovery...")
        task_cfg = self.config.get("partner", {})
        try:
            sheets = SheetsClient()
            gemini = GeminiClient()
            batch_service = BatchService()

            if not sheets.is_connected():
                logger.error("[AUTO PARTNER] Sheets is not connected.")
                return

            cat_code = CATEGORY_CODES.get(task_cfg.get("category", "All"), "ALL")
            batch_id = f"KP-{cat_code}-{datetime.now().strftime('%Y%m%d')}-AUTO"
            existing_domains = sheets.get_existing_partner_domains()

            batch_params = {
                "batch_id": batch_id,
                "vendor_match": "None (General search)",
                "category": task_cfg.get("category", "All"),
                "industries": "Technology & Telecom | Financial Services",
                "target_count": task_cfg.get("target_count", 5),
                "minimum_confidence_score": 70,
                "research_date": datetime.now().strftime("%Y-%m-%d"),
                "preferred_sources": "zdnet.co.kr, ddaily.co.kr, etnews.com",
                "max_discovery_candidates": 15,
                "exclude_small_agencies": True
            }

            report = gemini.run_partner_discovery_stage(batch_params, existing_domains)
            structured = gemini.run_partner_structuring_stage(batch_id, report, task_cfg.get("target_count", 5))
            raw_cands = structured.get("candidates", [])

            valid = []
            for c in raw_cands:
                domain = c.get("normalized_domain", "").strip().lower()
                if domain in existing_domains:
                    continue
                c["headquarters_country"] = "South Korea"
                c["korea_presence_found"] = "Yes"
                c["b2b_product_confirmed"] = "Yes"
                c["proprietary_product_confirmed"] = "Yes"
                c["review_status"] = "Auto-Collected"
                c["processing_status"] = "Completed"
                c["research_date"] = batch_params["research_date"]
                c["batch_id"] = batch_id
                valid.append(c)

            if valid:
                res = sheets.append_partners(valid)
                if res.get("success"):
                    batch_info = {
                        "batch_id": batch_id,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "region": "South Korea",
                        "category": batch_params["category"],
                        "industries": batch_params["industries"],
                        "candidate_count": len(raw_cands),
                        "saved_count": len(valid),
                        "status": "Completed (Auto-Collected)"
                    }
                    sheets.write_batch_log(batch_info)
                    batch_service.save_local_backup(batch_id, {"batch_id": batch_id, "candidates": valid, "status": "Auto-Saved"})

            if valid and task_cfg.get("email_enabled", False):
                self._send_job_email_report("partner", task_cfg, valid)

            self.config["partner"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["partner"]["last_status"] = f"Success ({len(valid)} saved)"
            self.save_config()
            logger.info(f"[AUTO PARTNER] Finished successfully. {len(valid)} saved.")

        except Exception as e:
            logger.error(f"[AUTO PARTNER] Failed: {e}")
            self.config["partner"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["partner"]["last_status"] = f"Failed: {e}"
            self.save_config()

    def _run_auto_news_job(self):
        logger.info("⏰ [AUTO TIMER] Starting scheduled News Discovery...")
        task_cfg = self.config.get("news", {})
        try:
            sheets = SheetsClient()
            gemini = GeminiClient()
            batch_service = BatchService()

            if not sheets.news_spreadsheet:
                logger.error("[AUTO NEWS] News sheet is not connected.")
                return

            cat_code = CATEGORY_CODES.get(task_cfg.get("primary_category", "All"), "ALL")
            batch_id = f"NEWS-{cat_code}-{datetime.now().strftime('%Y%m%d')}-AUTO"
            existing_urls = sheets.get_existing_news_urls()

            batch_params = {
                "batch_id": batch_id,
                "primary_category": task_cfg.get("primary_category", "All"),
                "news_topic": task_cfg.get("news_topic", "All"),
                "language": "All (EN + KO)",
                "target_count": task_cfg.get("target_count", 5),
                "research_date": datetime.now().strftime("%Y-%m-%d"),
                "preferred_sources": "zdnet.co.kr, etnews.com, techcrunch.com"
            }

            report = gemini.run_news_discovery_stage(batch_params, existing_urls)
            structured = gemini.run_news_structuring_stage(batch_id, report, task_cfg.get("target_count", 5))
            raw_news = structured.get("candidates", [])

            valid = []
            for a in raw_news:
                url = a.get("source_url", "").strip().lower()
                if url in existing_urls:
                    continue
                a["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                a["review_status"] = "Auto-Collected"
                a["batch_id"] = batch_id
                valid.append(a)

            if valid:
                res = sheets.append_news(valid)
                if res.get("success"):
                    batch_info = {
                        "batch_id": batch_id,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "region": "Global/Korea",
                        "category": batch_params["primary_category"],
                        "industries": batch_params["news_topic"],
                        "candidate_count": len(raw_news),
                        "saved_count": len(valid),
                        "status": "Completed (Auto-Collected)"
                    }
                    sheets.write_batch_log(batch_info)
                    batch_service.save_local_backup(batch_id, {"batch_id": batch_id, "candidates": valid, "status": "Auto-Saved"})

            if valid and task_cfg.get("email_enabled", False):
                self._send_job_email_report("news", task_cfg, valid)

            self.config["news"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["news"]["last_status"] = f"Success ({len(valid)} saved)"
            self.save_config()
            logger.info(f"[AUTO NEWS] Finished successfully. {len(valid)} saved.")

        except Exception as e:
            logger.error(f"[AUTO NEWS] Failed: {e}")
            self.config["news"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["news"]["last_status"] = f"Failed: {e}"
            self.save_config()

    def _send_job_email_report(self, task_type: str, task_cfg: Dict[str, Any], candidates: List[Dict[str, Any]]):
        recipient = task_cfg.get("recipient_email") or os.getenv("EMAIL_RECEIVER", "changwan.lim@agichang.ai")
        try:
            from services.email_service import EmailService
            email_svc = EmailService()
            if not email_svc.is_configured():
                logger.warning(f"[AUTO EMAIL] Cannot send email. EMAIL_SENDER / EMAIL_PASSWORD not set in environment.")
                return

            if task_type == "news":
                subject = f"⚡ [AIKA] 자동 수집 AI 뉴스 브리핑 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) - 총 {len(candidates)}건"
                html_body = email_svc.build_daily_digest_html(morning_news=candidates, evening_news=[])
            else:
                title_name = "벤더" if task_type == "vendor" else "국내 파트너"
                subject = f"⚡ [AIKA] 자동 수집 AI {title_name} 리포트 ({datetime.now().strftime('%Y-%m-%d')}) - 총 {len(candidates)}건"
                items_html = "".join([f"<li><b>{c.get('vendor_name') or c.get('company_name', '무명')}</b> ({c.get('normalized_domain', '')}): {c.get('one_line_summary', '')}</li>" for c in candidates])
                html_body = f"""<h2>AIKA 자동 수집 {title_name} 결과</h2>
                <p>수집 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>신규 저장 건수: <b>{len(candidates)}건</b></p>
                <ul>{items_html}</ul>
                """

            email_svc.send_email(subject=subject, html_body=html_body, to_email=recipient)
            logger.info(f"[AUTO EMAIL] Sent digest email to {recipient}")
        except Exception as e:
            logger.error(f"[AUTO EMAIL] Failed to send email: {e}")

    def _make_email_runner(self, task_name: str):
        """Helper to create bound function for scheduled email job runner."""
        def runner():
            self._run_scheduled_email_job(task_name)
        return runner

    def _run_scheduled_email_job(self, task_name: str):
        """Runs scheduled email dispatch job at specified email_dispatch_time."""
        logger.info(f"⏰ [AUTO EMAIL DISPATCH] Executing scheduled email dispatch for task '{task_name}'...")
        task_cfg = self.config.get(task_name, {})
        if not task_cfg.get("email_enabled", False):
            return

        try:
            sheets = SheetsClient()
            batch_service = BatchService()

            if task_name == "news":
                recent_news = batch_service.get_latest_batch_candidates("news") or []
                if not recent_news and sheets.news_spreadsheet:
                    try:
                        wks = sheets.news_spreadsheet.worksheet(sheets.news_sheet_name)
                        rows = wks.get_all_records()
                        if rows:
                            recent_news = []
                            for r in rows[-10:]:
                                recent_news.append({
                                    "title": str(r.get("Title", "")),
                                    "korean_title": str(r.get("Korean Title") or r.get("Title", "")),
                                    "source_media": str(r.get("Source Media", "")),
                                    "source_url": str(r.get("Source URL", "")),
                                    "published_date": str(r.get("Published Date", "")),
                                    "primary_ai_category": str(r.get("Primary AI Category", "")),
                                    "news_topic": str(r.get("News Topic", "")),
                                    "korean_summary": str(r.get("Korean Summary", "")),
                                    "detailed_summary": str(r.get("Detailed 10-Line Summary", "")),
                                    "key_keywords": str(r.get("Key Keywords", "")),
                                    "korea_market_relevance": str(r.get("Korea Market Relevance", "Medium"))
                                })
                    except Exception as sheet_err:
                        logger.warning(f"Failed reading sheets for email dispatch: {sheet_err}")

                if recent_news:
                    self._send_job_email_report("news", task_cfg, recent_news)
                else:
                    logger.info("[AUTO EMAIL DISPATCH] No recent news available to send.")
            else:
                recent = batch_service.get_latest_batch_candidates(task_name) or []
                if recent:
                    self._send_job_email_report(task_name, task_cfg, recent)
        except Exception as e:
            logger.error(f"[AUTO EMAIL DISPATCH] Exception during scheduled email dispatch: {e}")

    def send_test_email(self, task_type: str, recipient_email: str) -> Dict[str, Any]:
        """Sends a test email to verify SMTP configuration and HTML formatting."""
        try:
            from services.email_service import EmailService
            email_svc = EmailService()
            if not email_svc.is_configured():
                return {"success": False, "error": ".env 파일에 EMAIL_SENDER 및 EMAIL_PASSWORD가 설정되어 있지 않습니다."}

            sample_news = [{
                "title": "Sample AI Breakthrough Article",
                "korean_title": "AIKA 자동 예약 테스트: 최신 AI 기술 및 시장 동향 브리핑",
                "source_media": "AIKA News Intelligence",
                "published_date": datetime.now().strftime("%Y-%m-%d"),
                "source_url": "https://zdnet.co.kr",
                "primary_ai_category": "General AI",
                "news_topic": "AI Industry Trends",
                "korean_summary": "본 메일은 AIKA 뉴스 자동 예약 수집 및 결과 알림 발송 테스트 메일입니다.",
                "detailed_summary": "• 수집 시간: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n• 메일 발송 수신자: " + recipient_email + "\n• 설정된 횟수 및 시각에 따라 수집 완료 후 자동 발송됩니다.",
                "key_keywords": "AIKA, 뉴스 브리핑, 자동 예약, 테스트",
                "korea_market_relevance": "High"
            }]

            subject = f"🧪 [AIKA 테스트] 뉴스 자동 예약 알림 메일 테스트 ({datetime.now().strftime('%H:%M:%S')})"
            html_body = email_svc.build_daily_digest_html(morning_news=sample_news, evening_news=[])
            res = email_svc.send_email(subject=subject, html_body=html_body, to_email=recipient_email)
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_job_info(self, task_name: str) -> Dict[str, Any]:
        """Returns info about a task's job status and next run time."""
        cfg = self.config.get(task_name, {})
        next_run_times = []
        for job in self.scheduler.get_jobs():
            if job.id.startswith(f"auto_{task_name}_job") and job.next_run_time:
                next_run_times.append(job.next_run_time)

        if next_run_times:
            earliest_next = min(next_run_times)
            next_run_str = earliest_next.strftime("%Y-%m-%d %H:%M:%S")
        else:
            next_run_str = "None"

        return {
            "enabled": cfg.get("enabled", False),
            "mode": cfg.get("mode", "interval"),
            "last_run": cfg.get("last_run", "None"),
            "last_status": cfg.get("last_status", "Idle"),
            "next_run": next_run_str
        }
