import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# Load env configurations
spreadsheet_id = os.getenv("KOREAN_PARTNERS_SPREADSHEET_ID")
if not spreadsheet_id:
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
partner_sheet_name = os.getenv("KOREAN_PARTNERS_SHEET_NAME", "05_Korean_Partners")

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
key_path = os.path.join(os.getcwd(), "service_account.json")

HEADERS_PARTNER = [
    "No.", "Batch ID", "Company Name", "Official Website", "Normalized Domain",
    "Headquarters Country", "Main AI Product", "Primary AI Category", "Secondary AI Categories",
    "Company Summary", "Target Customers", "Target Industries", "Main Use Cases", "Deployment Type",
    "Official Product Page", "Official About Page", "Official Contact Page", "Korea Presence Found",
    "Potential Korean Partner Type", "Korea Market Relevance", "B2B Product Confirmed",
    "Proprietary Product Confirmed", "Confidence Score", "AIKA Recommendation", "Primary Evidence URL",
    "Additional Source URLs", "Review Status", "Processing Status", "Research Date", "Error Message", "Research Notes"
]

# Category sheets to create (matches ALLOWED_CATEGORIES in validator.py)
CATEGORY_SHEETS = [
    "AI Agents",
    "Generative AI",
    "Enterprise Automation",
    "AI Security",
    "AI Governance",
    "Data and AI Platform",
    "AI Observability",
    "Private AI",
    "Computer Vision",
    "Conversational AI",
    "Manufacturing AI",
    "Financial AI",
    "Healthcare AI",
    "Retail AI",
    "Marketing AI",
    "HR AI",
    "Developer Tools",
    "Other",
]

def get_or_create_worksheet(sh, title, rows=1000, cols=40):
    """Gets existing worksheet or creates a new one with given title."""
    try:
        wks = sh.worksheet(title)
        print(f"  [EXISTS] '{title}'")
        return wks
    except gspread.exceptions.WorksheetNotFound:
        wks = sh.add_worksheet(title=title, rows=str(rows), cols=str(cols))
        print(f"  [CREATED] '{title}'")
        return wks

def setup_partner_sheet():
    print(f"Connecting to Spreadsheet ID: {spreadsheet_id}")
    creds = Credentials.from_service_account_file(key_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_id)

    # 1. Create / initialize the master "All Partners" sheet
    print(f"\n[1/2] Setting up master sheet: '{partner_sheet_name}'")
    wks_all = get_or_create_worksheet(sh, partner_sheet_name)
    wks_all.clear()
    wks_all.update([HEADERS_PARTNER], "A1", value_input_option="USER_ENTERED")
    print(f"  [OK] Initialized '{partner_sheet_name}' with {len(HEADERS_PARTNER)} column headers.")

    # 2. Create / initialize each category sheet
    print(f"\n[2/2] Setting up {len(CATEGORY_SHEETS)} category sheets...")
    for cat in CATEGORY_SHEETS:
        wks_cat = get_or_create_worksheet(sh, cat)
        wks_cat.clear()
        wks_cat.update([HEADERS_PARTNER], "A1", value_input_option="USER_ENTERED")

    print(f"\n[DONE] Created 1 master sheet + {len(CATEGORY_SHEETS)} category sheets.")

if __name__ == "__main__":
    setup_partner_sheet()
