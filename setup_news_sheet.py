import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

spreadsheet_id = os.getenv("NEWS_SPREADSHEET_ID")
news_sheet_name = os.getenv("NEWS_SHEET_NAME", "06_News_All")

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
key_path = os.path.join(os.getcwd(), "service_account.json")

NEWS_HEADERS = [
    "No.", "Batch ID", "수집일시", "기사 게재일", "제목",
    "출처 미디어명", "출처 URL", "언어",
    "Primary AI Category", "News Topic",
    "관련 기업명", "한줄 요약", "10줄 상세 요약", "핵심 키워드",
    "한국 시장 관련성", "Review Status", "Research Notes"
]


# Primary Category sheets (same as vendor/partner for cross-DB matching)
PRIMARY_CATEGORY_SHEETS = [
    "AI Agents", "Generative AI", "Enterprise Automation", "AI Security",
    "AI Governance", "Data and AI Platform", "AI Observability", "Private AI",
    "Computer Vision", "Conversational AI", "Manufacturing AI", "Financial AI",
    "Healthcare AI", "Retail AI", "Marketing AI", "HR AI", "Developer Tools", "Other",
]

def get_or_create_worksheet(sh, title, rows=2000, cols=20):
    try:
        wks = sh.worksheet(title)
        print(f"  [EXISTS] '{title}'")
        return wks
    except gspread.exceptions.WorksheetNotFound:
        wks = sh.add_worksheet(title=title, rows=str(rows), cols=str(cols))
        print(f"  [CREATED] '{title}'")
        return wks

def setup_news_sheet():
    print(f"Connecting to News Spreadsheet ID: {spreadsheet_id}")
    creds = Credentials.from_service_account_file(key_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_id)

    # 1. Master sheet
    print(f"\n[1/2] Setting up master sheet: '{news_sheet_name}'")
    wks_all = get_or_create_worksheet(sh, news_sheet_name)
    wks_all.clear()
    wks_all.update([NEWS_HEADERS], "A1", value_input_option="USER_ENTERED")
    print(f"  [OK] Initialized '{news_sheet_name}' with {len(NEWS_HEADERS)} columns.")

    # 2. Primary Category sheets
    print(f"\n[2/2] Setting up {len(PRIMARY_CATEGORY_SHEETS)} Primary Category sheets...")
    for cat in PRIMARY_CATEGORY_SHEETS:
        wks_cat = get_or_create_worksheet(sh, cat)
        wks_cat.clear()
        wks_cat.update([NEWS_HEADERS], "A1", value_input_option="USER_ENTERED")

    print(f"\n[DONE] Created 1 master + {len(PRIMARY_CATEGORY_SHEETS)} category sheets in news spreadsheet.")

if __name__ == "__main__":
    setup_news_sheet()
