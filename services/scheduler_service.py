import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
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
        "daily_time": "09:00",
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
        "daily_time": "09:00",
        "target_count": 5,
        "category": "All",
        "last_run": None,
        "last_status": "Idle"
    },
    "news": {
        "enabled": False,
        "mode": "interval",
        "interval_hours": 6,
        "daily_time": "08:00",
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
        for task_name in ["vendor", "partner", "news"]:
            job_id = f"auto_{task_name}_job"
            task_cfg = self.config.get(task_name, {})

            # Remove existing job if present
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            if task_cfg.get("enabled", False):
                mode = task_cfg.get("mode", "interval")
                if mode == "interval":
                    hours = max(1, int(task_cfg.get("interval_hours", 24)))
                    trigger = IntervalTrigger(hours=hours)
                else: # daily
                    time_str = task_cfg.get("daily_time", "09:00")
                    try:
                        hh, mm = map(int, time_str.split(":"))
                    except Exception:
                        hh, mm = 9, 0
                    trigger = CronTrigger(hour=hh, minute=mm)

                func_map = {
                    "vendor": self._run_auto_vendor_job,
                    "partner": self._run_auto_partner_job,
                    "news": self._run_auto_news_job
                }

                self.scheduler.add_job(
                    func=func_map[task_name],
                    trigger=trigger,
                    id=job_id,
                    replace_existing=True
                )
                logger.info(f"Scheduled job '{job_id}' with mode '{mode}'")

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

            self.config["news"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["news"]["last_status"] = f"Success ({len(valid)} saved)"
            self.save_config()
            logger.info(f"[AUTO NEWS] Finished successfully. {len(valid)} saved.")

        except Exception as e:
            logger.error(f"[AUTO NEWS] Failed: {e}")
            self.config["news"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config["news"]["last_status"] = f"Failed: {e}"
            self.save_config()

    def get_job_info(self, task_name: str) -> Dict[str, Any]:
        """Returns info about a task's job status and next run time."""
        job_id = f"auto_{task_name}_job"
        job = self.scheduler.get_job(job_id)
        cfg = self.config.get(task_name, {})
        next_run_str = str(job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")) if job and job.next_run_time else "None"
        return {
            "enabled": cfg.get("enabled", False),
            "mode": cfg.get("mode", "interval"),
            "last_run": cfg.get("last_run", "None"),
            "last_status": cfg.get("last_status", "Idle"),
            "next_run": next_run_str
        }
