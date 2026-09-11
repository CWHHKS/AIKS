import os
import json
import logging
from typing import List, Dict, Any, Optional
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve setting from os.environ first, then streamlit.secrets if available."""
    val = os.getenv(key)
    if val:
        return str(val).strip()
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default

class SheetsClient:
    def __init__(self):
        self.last_error = None
        self.spreadsheet_id = _get_setting("GOOGLE_SPREADSHEET_ID")
        self.partner_spreadsheet_id = _get_setting("KOREAN_PARTNERS_SPREADSHEET_ID")
        self.news_spreadsheet_id = _get_setting("NEWS_SPREADSHEET_ID")
        self.key_filepath = os.path.join(os.getcwd(), "service_account.json")
        self.client = None
        self.spreadsheet = None
        self.partner_spreadsheet = None
        self.news_spreadsheet = None

        # Sheet names from environment or defaults
        self.vendor_sheet_name = _get_setting("VENDOR_SHEET_NAME", "01_Vendor_Candidates")
        self.batch_log_sheet_name = _get_setting("BATCH_LOG_SHEET_NAME", "02_Batch_Log")
        self.error_log_sheet_name = _get_setting("ERROR_LOG_SHEET_NAME", "03_Error_Log")
        self.partner_sheet_name = _get_setting("KOREAN_PARTNERS_SHEET_NAME", "05_Korean_Partners")
        self.news_sheet_name = _get_setting("NEWS_SHEET_NAME", "06_News_All")
        
        self._connect()

    def _connect(self):
        """
        Attempts connection using service account credentials.
        Priority:
          1. Local service_account.json file
          2. Streamlit Secrets (st.secrets["gcp_service_account"])
          3. Environment variable GCP_SERVICE_ACCOUNT_JSON
        """
        if not self.spreadsheet_id:
            self.last_error = "GOOGLE_SPREADSHEET_ID is not configured in environment or secrets."
            logger.warning(self.last_error)
            return

        creds = None
        # 1. Local file
        if os.path.exists(self.key_filepath):
            try:
                creds = Credentials.from_service_account_file(self.key_filepath, scopes=SCOPES)
                logger.info("Loaded Google credentials from local service_account.json")
            except Exception as e:
                logger.warning(f"Failed to load credentials from file {self.key_filepath}: {e}")

        # 2. Streamlit Secrets
        if not creds:
            try:
                import streamlit as st
                if "gcp_service_account" in st.secrets:
                    sa_info = dict(st.secrets["gcp_service_account"])
                    if "private_key" in sa_info and isinstance(sa_info["private_key"], str):
                        # Fix escaped newlines if present
                        sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")
                    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
                    logger.info("Loaded Google credentials from st.secrets['gcp_service_account']")
            except Exception as e:
                self.last_error = f"Secrets auth error: {e}"
                logger.error(self.last_error)

        # 3. GCP_SERVICE_ACCOUNT_JSON environment variable
        if not creds:
            env_sa = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
            if env_sa:
                try:
                    sa_info = json.loads(env_sa)
                    if "private_key" in sa_info and isinstance(sa_info["private_key"], str):
                        sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")
                    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
                    logger.info("Loaded Google credentials from GCP_SERVICE_ACCOUNT_JSON env var")
                except Exception as e:
                    self.last_error = f"Env auth error: {e}"
                    logger.warning(self.last_error)

        if not creds:
            if not self.last_error:
                self.last_error = "No Google service account found in [gcp_service_account] secrets."
            logger.warning(self.last_error)
            return

        try:
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            if self.partner_spreadsheet_id:
                self.partner_spreadsheet = self.client.open_by_key(self.partner_spreadsheet_id)
                logger.info("Connected to separate Korean Partners spreadsheet.")
            else:
                self.partner_spreadsheet = self.spreadsheet
                logger.info("Connected to default spreadsheet for partners.")

            if self.news_spreadsheet_id:
                self.news_spreadsheet = self.client.open_by_key(self.news_spreadsheet_id)
                logger.info("Connected to News Intelligence spreadsheet.")
            self.last_error = None
        except Exception as e:
            self.last_error = f"Sheets connection error: {str(e)}"
            logger.error(self.last_error)
            self.client = None
            self.spreadsheet = None
            self.partner_spreadsheet = None
            self.news_spreadsheet = None

    def is_connected(self) -> bool:
        """Returns True if successfully authorized and connected to the spreadsheet."""
        if not self.client or not self.spreadsheet:
            # Try connecting again in case the file was added later
            self._connect()
        return self.client is not None and self.spreadsheet is not None

    def get_registered_vendor_count(self) -> int:
        """Gets total count of vendors in the vendor candidates sheet."""
        if not self.is_connected():
            return 0
        try:
            wks = self.spreadsheet.worksheet(self.vendor_sheet_name)
            # Total rows minus header
            row_count = len(wks.get_all_values())
            return max(0, row_count - 1)
        except Exception as e:
            logger.error(f"Error getting vendor count: {str(e)}")
            return 0

    def get_existing_domains(self) -> List[str]:
        """
        Retrieves all normalized domains currently in the Google Sheet (Column 4).
        """
        if not self.is_connected():
            logger.warning("SheetsClient is disconnected. Returning empty domain list.")
            return []
            
        try:
            wks = self.spreadsheet.worksheet(self.vendor_sheet_name)
            # Column 5 corresponds to Normalized Domain (since Column 1 is 'No.').
            domains = wks.col_values(5)
            if len(domains) > 1:
                # Remove header row ('Normalized Domain') and strip whitespace
                return [d.strip().lower() for d in domains[1:] if d.strip()]
            return []
        except Exception as e:
            logger.error(f"Failed to fetch existing domains from sheet: {str(e)}")
            return []

    def append_vendors(self, vendors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Appends vendor rows to the '01_Vendor_Candidates' worksheet.
        """
        if not self.is_connected():
            return {"success": False, "error": "Google Sheets API is not connected."}
            
        try:
            wks = self.spreadsheet.worksheet(self.vendor_sheet_name)
            rows_to_append = []
            
            # Calculate next sequential number
            current_rows = len(wks.get_all_values())
            next_idx = current_rows if current_rows > 0 else 1
            
            for v in vendors:
                row = [
                    next_idx, # No.
                    v.get("batch_id", ""),
                    v.get("company_name", ""),
                    v.get("official_website", ""),
                    v.get("normalized_domain", ""),
                    v.get("headquarters_country", ""),
                    v.get("main_ai_product", ""),
                    v.get("primary_ai_category", ""),
                    v.get("secondary_ai_categories", ""),
                    v.get("company_summary", ""),
                    v.get("target_customers", ""),
                    v.get("target_industries", ""),
                    v.get("main_use_cases", ""),
                    v.get("deployment_type", ""),
                    v.get("official_product_page", ""),
                    v.get("official_about_page", ""),
                    v.get("official_contact_page", ""),
                    v.get("korea_presence_found", ""),
                    v.get("potential_korean_partner_type", ""),
                    v.get("korea_market_relevance", ""),
                    v.get("b2b_product_confirmed", ""),
                    v.get("proprietary_product_confirmed", ""),
                    v.get("confidence_score", ""),
                    v.get("aika_recommendation", ""),
                    v.get("primary_evidence_url", ""),
                    v.get("additional_source_urls", ""),
                    v.get("review_status", "New"),
                    v.get("processing_status", "Completed"),
                    v.get("research_date", ""),
                    v.get("error_message", ""),
                    v.get("research_notes", "")
                ]
                rows_to_append.append(row)
                next_idx += 1
                
            wks.append_rows(rows_to_append, value_input_option="RAW")
            logger.info(f"Appended {len(rows_to_append)} vendors to {self.vendor_sheet_name}.")
            return {"success": True, "count": len(rows_to_append)}
            
        except Exception as e:
            logger.error(f"Failed to append vendors to Google Sheets: {str(e)}")
            return {"success": False, "error": str(e)}

    def write_batch_log(self, batch_info: Dict[str, Any]) -> bool:
        """
        Logs batch execution details in '02_Batch_Log'.
        Columns: Batch ID, Run Timestamp, Region, Category, Target Industries, Candidate Count, Saved Count, Status
        """
        if not self.is_connected():
            return False
            
        try:
            wks = self.spreadsheet.worksheet(self.batch_log_sheet_name)
            current_rows = len(wks.get_all_values())
            next_idx = current_rows if current_rows > 0 else 1
            row = [
                next_idx, # No.
                batch_info.get("batch_id", ""),
                batch_info.get("timestamp", ""),
                batch_info.get("region", ""),
                batch_info.get("category", ""),
                batch_info.get("industries", ""),
                batch_info.get("candidate_count", 0),
                batch_info.get("saved_count", 0),
                batch_info.get("status", "Completed")
            ]
            wks.append_row(row, value_input_option="RAW")
            return True
        except Exception as e:
            logger.error(f"Failed to write batch log: {str(e)}")
            return False

    def write_error_log(self, batch_id: str, error_msg: str, component: str, timestamp: str) -> bool:
        """
        Logs error messages in '03_Error_Log'.
        Columns: Batch ID, Timestamp, Component, Error Message
        """
        if not self.is_connected():
            return False
            
        try:
            wks = self.spreadsheet.worksheet(self.error_log_sheet_name)
            current_rows = len(wks.get_all_values())
            next_idx = current_rows if current_rows > 0 else 1
            row = [next_idx, batch_id, timestamp, component, error_msg]
            wks.append_row(row, value_input_option="RAW")
            return True
        except Exception as e:
            logger.error(f"Failed to write error log: {str(e)}")
            return False

    def get_recent_batches(self, limit: int = 10) -> List[List[str]]:
        """
        Gets the last N batch logs.
        """
        if not self.is_connected():
            return []
            
        try:
            wks = self.spreadsheet.worksheet(self.batch_log_sheet_name)
            all_rows = wks.get_all_values()
            if len(all_rows) <= 1:
                return []
            # Return last N rows, reversed (newest first)
            data_rows = all_rows[1:]
            data_rows.reverse()
            return data_rows[:limit]
        except Exception as e:
            logger.error(f"Failed to fetch recent batches: {str(e)}")
            return []

    def get_registered_vendors(self) -> List[str]:
        """
        Retrieves a sorted list of registered vendor company names from Column 3 of the vendor sheet.
        """
        if not self.is_connected():
            return []
        try:
            wks = self.spreadsheet.worksheet(self.vendor_sheet_name)
            names = wks.col_values(3) # Column 3 is Company Name
            if len(names) > 1:
                # Remove header row ('Company Name') and strip whitespace
                vendor_names = list(set([n.strip() for n in names[1:] if n.strip()]))
                vendor_names.sort()
                return vendor_names
            return []
        except Exception as e:
            logger.error(f"Failed to fetch registered vendors: {str(e)}")
            return []

    def get_registered_partner_count(self) -> int:
        """Gets total count of partners in the partner candidates sheet."""
        if not self.is_connected() or not self.partner_spreadsheet:
            return 0
        try:
            wks = self.partner_spreadsheet.worksheet(self.partner_sheet_name)
            row_count = len(wks.get_all_values())
            return max(0, row_count - 1)
        except Exception as e:
            logger.error(f"Error getting partner count: {str(e)}")
            return 0

    def get_existing_partner_domains(self) -> List[str]:
        """Retrieves all normalized partner domains currently in the partner sheet."""
        if not self.is_connected() or not self.partner_spreadsheet:
            return []
        try:
            wks = self.partner_spreadsheet.worksheet(self.partner_sheet_name)
            domains = wks.col_values(5) # Column 5 corresponds to Normalized Domain
            if len(domains) > 1:
                return [d.strip().lower() for d in domains[1:] if d.strip()]
            return []
        except Exception as e:
            logger.error(f"Failed to fetch partner domains: {str(e)}")
            return []

    def _to_str(self, val) -> str:
        """Converts a value to a Google Sheets-safe string. Lists are joined with ', '."""
        if isinstance(val, list):
            return ", ".join(str(v) for v in val if v)
        if val is None:
            return ""
        return str(val)

    def _build_partner_row(self, v: Dict[str, Any], idx: int) -> List:
        """Builds a single partner row list in the correct 31-column order."""
        s = self._to_str
        return [
            idx,
            s(v.get("batch_id", "")),
            s(v.get("company_name", "")),
            s(v.get("official_website", "")),
            s(v.get("normalized_domain", "")),
            s(v.get("headquarters_country", "")),
            s(v.get("main_ai_product", "")),
            s(v.get("primary_ai_category", "")),
            s(v.get("secondary_ai_categories", "")),
            s(v.get("company_summary", "")),
            s(v.get("target_customers", "")),
            s(v.get("target_industries", "")),
            s(v.get("main_use_cases", "")),
            s(v.get("deployment_type", "")),
            s(v.get("official_product_page", "")),
            s(v.get("official_about_page", "")),
            s(v.get("official_contact_page", "")),
            s(v.get("korea_presence_found", "")),
            s(v.get("potential_korean_partner_type", "")),
            s(v.get("korea_market_relevance", "")),
            s(v.get("b2b_product_confirmed", "")),
            s(v.get("proprietary_product_confirmed", "")),
            s(v.get("confidence_score", "")),
            s(v.get("aika_recommendation", "")),
            s(v.get("primary_evidence_url", "")),
            s(v.get("additional_source_urls", "")),
            s(v.get("review_status", "New")),
            s(v.get("processing_status", "Completed")),
            s(v.get("research_date", "")),
            s(v.get("error_message", "")),
            s(v.get("research_notes", ""))
        ]


    def append_partners(self, partners: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        1) Appends all partner rows to the master '05_Korean_Partners' sheet.
        2) Also appends each partner to the matching category sheet (e.g. 'AI Security').
           If the category sheet does not exist yet, it is created automatically.
        """
        if not self.is_connected() or not self.partner_spreadsheet:
            return {"success": False, "error": "Google Sheets API is not connected."}

        try:
            # ── STEP 1: Write to master sheet ──────────────────────────────
            master_wks = self.partner_spreadsheet.worksheet(self.partner_sheet_name)
            current_rows = len(master_wks.get_all_values())
            next_idx = current_rows if current_rows > 0 else 1

            master_rows = []
            for v in partners:
                master_rows.append(self._build_partner_row(v, next_idx))
                next_idx += 1

            master_wks.append_rows(master_rows, value_input_option="RAW")
            logger.info(f"Appended {len(master_rows)} partners to master sheet '{self.partner_sheet_name}'.")

            # ── STEP 2: Distribute to category sheets ──────────────────────
            # Group partners by primary_ai_category
            category_groups: Dict[str, List[Dict]] = {}
            for v in partners:
                cat = v.get("primary_ai_category", "Other").strip() or "Other"
                category_groups.setdefault(cat, []).append(v)

            headers = [
                "No.", "Batch ID", "Company Name", "Official Website", "Normalized Domain",
                "Headquarters Country", "Main AI Product", "Primary AI Category", "Secondary AI Categories",
                "Company Summary", "Target Customers", "Target Industries", "Main Use Cases", "Deployment Type",
                "Official Product Page", "Official About Page", "Official Contact Page", "Korea Presence Found",
                "Potential Korean Partner Type", "Korea Market Relevance", "B2B Product Confirmed",
                "Proprietary Product Confirmed", "Confidence Score", "AIKA Recommendation", "Primary Evidence URL",
                "Additional Source URLs", "Review Status", "Processing Status", "Research Date", "Error Message", "Research Notes"
            ]

            for cat, cat_partners in category_groups.items():
                try:
                    cat_wks = self.partner_spreadsheet.worksheet(cat)
                except Exception:
                    # Auto-create the category sheet if it doesn't exist
                    cat_wks = self.partner_spreadsheet.add_worksheet(title=cat, rows="1000", cols="40")
                    cat_wks.update([headers], "A1", value_input_option="USER_ENTERED")
                    logger.info(f"Auto-created category sheet: '{cat}'")

                cat_rows_count = len(cat_wks.get_all_values())
                cat_next_idx = cat_rows_count if cat_rows_count > 0 else 1

                cat_rows = []
                for v in cat_partners:
                    cat_rows.append(self._build_partner_row(v, cat_next_idx))
                    cat_next_idx += 1

                cat_wks.append_rows(cat_rows, value_input_option="RAW")
                logger.info(f"  → Distributed {len(cat_rows)} partners to category sheet '{cat}'.")

            return {"success": True, "count": len(master_rows)}

        except Exception as e:
            logger.error(f"Failed to append partners to Google Sheets: {str(e)}")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # NEWS INTELLIGENCE METHODS
    # ═══════════════════════════════════════════════════════════════

    def get_registered_news_count(self) -> int:
        """Gets total count of news articles in the master news sheet."""
        if not self.news_spreadsheet:
            return 0
        try:
            wks = self.news_spreadsheet.worksheet(self.news_sheet_name)
            return max(0, len(wks.get_all_values()) - 1)
        except Exception as e:
            logger.error(f"Error getting news count: {str(e)}")
            return 0

    def get_existing_news_urls(self) -> List[str]:
        """Retrieves all source URLs already saved to avoid duplicates (Column 7)."""
        if not self.news_spreadsheet:
            return []
        try:
            wks = self.news_spreadsheet.worksheet(self.news_sheet_name)
            urls = wks.col_values(7)  # "출처 URL" column
            return [u.strip().lower() for u in urls[1:] if u.strip()]
        except Exception as e:
            logger.error(f"Failed to fetch existing news URLs: {str(e)}")
            return []

    def _build_news_row(self, a: Dict[str, Any], idx: int) -> List:
        """Builds a single news article row in the correct 16-column order."""
        s = self._to_str
        title_orig = a.get("title", "")
        title_kr = a.get("korean_title", "")
        if title_kr and title_kr.strip() != title_orig.strip():
            title_display = f"{title_orig}\n({title_kr})"
        else:
            title_display = title_orig

        return [
            idx,
            s(a.get("batch_id", "")),
            s(a.get("collected_at", "")),
            s(a.get("published_date", "")),
            s(title_display),
            s(a.get("source_media", "")),
            s(a.get("source_url", "")),
            s(a.get("language", "EN")),
            s(a.get("primary_ai_category", "")),
            s(a.get("news_topic", "")),
            s(a.get("related_companies", "")),
            s(a.get("korean_summary", "")),
            s(a.get("detailed_summary", "")),
            s(a.get("key_keywords", "")),
            s(a.get("korea_market_relevance", "")),
            s(a.get("review_status", "New")),
            s(a.get("research_notes", "")),
        ]


    def append_news(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        1) Appends all articles to the master '06_News_All' sheet.
        2) Distributes each article to its matching Primary AI Category sheet.
        """
        if not self.news_spreadsheet:
            return {"success": False, "error": "News spreadsheet is not connected."}

        news_headers = [
            "No.", "Batch ID", "수집일시", "기사 게재일", "제목",
            "출처 미디어명", "출처 URL", "언어",
            "Primary AI Category", "News Topic",
            "관련 기업명", "한줄 요약", "10줄 상세 요약", "핵심 키워드",
            "한국 시장 관련성", "Review Status", "Research Notes"
        ]


        try:
            # ── STEP 1: Write to master sheet ──────────────────────
            master_wks = self.news_spreadsheet.worksheet(self.news_sheet_name)
            current_rows = len(master_wks.get_all_values())
            next_idx = current_rows if current_rows > 0 else 1

            master_rows = []
            for a in articles:
                master_rows.append(self._build_news_row(a, next_idx))
                next_idx += 1

            master_wks.append_rows(master_rows, value_input_option="RAW")
            logger.info(f"Appended {len(master_rows)} articles to '{self.news_sheet_name}'.")

            # ── STEP 2: Distribute to Primary AI Category sheets ───
            category_groups: Dict[str, List[Dict]] = {}
            for a in articles:
                cat = a.get("primary_ai_category", "Other").strip() or "Other"
                category_groups.setdefault(cat, []).append(a)

            for cat, cat_articles in category_groups.items():
                try:
                    cat_wks = self.news_spreadsheet.worksheet(cat)
                except Exception:
                    cat_wks = self.news_spreadsheet.add_worksheet(title=cat, rows="2000", cols="20")
                    cat_wks.update([news_headers], "A1", value_input_option="USER_ENTERED")
                    logger.info(f"Auto-created news category sheet: '{cat}'")

                cat_count = len(cat_wks.get_all_values())
                cat_idx = cat_count if cat_count > 0 else 1
                cat_rows = []
                for a in cat_articles:
                    cat_rows.append(self._build_news_row(a, cat_idx))
                    cat_idx += 1
                cat_wks.append_rows(cat_rows, value_input_option="RAW")
                logger.info(f"  → {len(cat_rows)} articles → '{cat}'")

            return {"success": True, "count": len(master_rows)}

        except Exception as e:
            logger.error(f"Failed to append news: {str(e)}")
            return {"success": False, "error": str(e)}
