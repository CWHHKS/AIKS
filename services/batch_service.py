import os
import json
import logging
import glob
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

CATEGORY_CODES = {
    "All": "ALL",
    "AI Agents": "AGENT",
    "Generative AI": "GENAI",
    "Enterprise Automation": "AUTO",
    "AI Security": "AISEC",
    "AI Governance": "GOV",
    "Data and AI Platform": "DATA",
    "AI Observability": "OBSER",
    "Private AI": "PRIV",
    "Computer Vision": "VISION",
    "Conversational AI": "CONV",
    "Manufacturing AI": "MFG",
    "Financial AI": "FIN",
    "Healthcare AI": "HLTH",
    "Retail AI": "RTL",
    "Marketing AI": "MKT",
    "HR AI": "HRAI",
    "Developer Tools": "DEV",
    "Other": "OTH"
}

class BatchService:
    def __init__(self):
        self.backup_dir = os.path.join(os.getcwd(), "data", "local_backup")
        self.cache_dir = os.path.join(os.getcwd(), "data", "batch_cache")
        
        # Create directories if they do not exist
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

    def generate_batch_id(self, category_name: str) -> str:
        """
        Generates Batch ID following the rule: GV + Category Code + Date + Sequence.
        Example: GV-AISEC-20260803-01
        """
        cat_code = CATEGORY_CODES.get(category_name, "VEND")
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Count existing backup files for today to determine sequence
        search_pattern = os.path.join(self.backup_dir, f"GV-{cat_code}-{date_str}-*.json")
        existing_files = glob.glob(search_pattern)
        
        sequence = len(existing_files) + 1
        seq_str = f"{sequence:02d}"
        
        return f"GV-{cat_code}-{date_str}-{seq_str}"

    def save_local_backup(self, batch_id: str, data: Dict[str, Any]) -> str:
        """
        Saves research session data to a local JSON file.
        Returns the path of the saved file.
        """
        filename = f"{batch_id}.json"
        filepath = os.path.join(self.backup_dir, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Session backup saved successfully to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save local backup JSON: {str(e)}")
            raise e

    def load_local_backup(self, batch_id: str) -> Dict[str, Any]:
        """
        Loads a session from the local JSON backup by batch_id.
        """
        filename = f"{batch_id}.json"
        filepath = os.path.join(self.backup_dir, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Local backup for batch {batch_id} not found.")
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load local backup JSON: {str(e)}")
            raise e

    def save_audit_log(self, batch_id: str, audit_records: List[Dict[str, Any]]) -> str:
        """Saves detailed cross-verification audit logs to data/audit_logs/."""
        audit_dir = os.path.join(os.getcwd(), "data", "audit_logs")
        os.makedirs(audit_dir, exist_ok=True)
        filepath = os.path.join(audit_dir, f"{batch_id}_audit.json")
        try:
            payload = {
                "batch_id": batch_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "audit_provider": os.getenv("AUDIT_PROVIDER", "claude"),
                "claude_model": os.getenv("CLAUDE_AUDIT_MODEL", "claude-sonnet-4-6"),
                "total_records": len(audit_records),
                "records": audit_records
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"Detailed audit log saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")
            return ""

    def get_all_audit_logs(self) -> List[Dict[str, Any]]:
        """Returns all audit log files sorted by date."""
        audit_dir = os.path.join(os.getcwd(), "data", "audit_logs")
        if not os.path.exists(audit_dir):
            return []
        files = glob.glob(os.path.join(audit_dir, "*_audit.json"))
        files.sort(key=os.path.getmtime, reverse=True)
        logs = []
        for fp in files:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    logs.append(json.load(f))
            except Exception:
                continue
        return logs

    def get_backup_list(self) -> List[Dict[str, str]]:
        """
        Returns a list of all local backups with metadata.
        """
        backups = []
        search_pattern = os.path.join(self.backup_dir, "*.json")
        files = glob.glob(search_pattern)
        
        # Sort by creation time (newest first)
        files.sort(key=os.path.getmtime, reverse=True)
        
        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    backups.append({
                        "batch_id": data.get("batch_id", "Unknown"),
                        "research_date": data.get("research_date", data.get("timestamp", "")),
                        "category": data.get("primary_category", data.get("category", "")),
                        "region": data.get("region", "Global"),
                        "candidate_count": len(data.get("candidates", [])),
                        "saved_count": len(data.get("saved_candidates", [])),
                        "status": data.get("status", "Backup")
                    })
            except Exception:
                # Skip corrupt files
                continue
                
        return backups
