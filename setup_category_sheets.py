import os
import logging
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Category definition
CATEGORIES = [
    "AI Agents",
    "Generative AI",
    "Conversational AI",
    "Developer Tools",
    "Enterprise Automation",
    "Data and AI Platform",
    "Industrial AI",
    "Security AI",
    "Other"
]

spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
vendor_sheet_name = os.getenv("VENDOR_SHEET_NAME", "01_Vendor_Candidates")
key_path = os.path.join(os.getcwd(), "service_account.json")
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

if not spreadsheet_id:
    logger.error("Spreadsheet ID is missing in .env.")
    exit(1)

try:
    creds = Credentials.from_service_account_file(key_path, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)
    logger.info("Connected to Google Sheets successfully.")
    
    # Configure each category worksheet
    for category in CATEGORIES:
        logger.info(f"Setting up worksheet for category: '{category}'...")
        
        # Check if worksheet already exists
        try:
            wks = spreadsheet.worksheet(category)
            logger.info(f"Worksheet '{category}' already exists.")
        except gspread.WorksheetNotFound:
            # Create the worksheet
            wks = spreadsheet.add_worksheet(title=category, rows=1000, cols=32)
            logger.info(f"Created new worksheet '{category}'.")
            
        # Write the QUERY formula in cell A1
        formula = f'=IFERROR(QUERY(\'{vendor_sheet_name}\'!A:AF, "SELECT * WHERE H = \'{category}\'", 1), "")'
        
        # In newer gspread, update is: update(range_name, values, **kwargs)
        # To write USER_ENTERED formula, use value_input_option='USER_ENTERED'
        wks.update(range_name='A1', values=[[formula]], value_input_option='USER_ENTERED')
        logger.info(f"Successfully updated formula in '{category}' cell A1.")

    print("\nSUCCESS! All category worksheets have been configured with QUERY formulas.")
    
except Exception as e:
    logger.error(f"Error configuring worksheets: {e}")
