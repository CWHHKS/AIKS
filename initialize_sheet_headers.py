import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# Load env configurations
spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
vendor_sheet_name = os.getenv("VENDOR_SHEET_NAME", "01_Vendor_Candidates")
batch_log_sheet_name = os.getenv("BATCH_LOG_SHEET_NAME", "02_Batch_Log")
error_log_sheet_name = os.getenv("ERROR_LOG_SHEET_NAME", "03_Error_Log")

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
key_path = os.path.join(os.getcwd(), "service_account.json")

creds = Credentials.from_service_account_file(key_path, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(spreadsheet_id)

HEADERS_VENDOR = [
    "No.", "Batch ID", "Company Name", "Official Website", "Normalized Domain", 
    "Headquarters Country", "Main AI Product", "Primary AI Category", "Secondary AI Categories", 
    "Company Summary", "Target Customers", "Target Industries", "Main Use Cases", "Deployment Type", 
    "Official Product Page", "Official About Page", "Official Contact Page", "Korea Presence Found", 
    "Potential Korean Partner Type", "Korea Market Relevance", "B2B Product Confirmed", 
    "Proprietary Product Confirmed", "Confidence Score", "AIKA Recommendation", "Primary Evidence URL", 
    "Additional Source URLs", "Review Status", "Processing Status", "Research Date", "Error Message", "Research Notes"
]

HEADERS_BATCH = [
    "No.", "Batch ID", "Run Timestamp", "Region", "Category", 
    "Target Industries", "Candidates Found", "Saved Count", "Status"
]

HEADERS_ERROR = [
    "No.", "Batch ID", "Timestamp", "Component", "Error Message"
]

def initialize_sheets():
    print(f"Opening spreadsheet: {sh.title} ({spreadsheet_id})")
    
    # --- 1. Vendor Candidates sheet ---
    print(f"\n1. Initializing '{vendor_sheet_name}'...")
    wks_vendor = sh.worksheet(vendor_sheet_name)
    existing_values = wks_vendor.get_all_values()
    
    formatted_rows = []
    
    if len(existing_values) > 0:
        # Check if first row is already headers (e.g. contains 'No.' or 'Company Name')
        if existing_values[0][2] == "Company Name" or existing_values[0][0] == "No.":
            print("Headers already exist. Shifting/fixing existing data...")
            data_rows = existing_values[1:]
        else:
            print("No headers found. Converting existing data...")
            data_rows = existing_values
            
        # Refactor existing data rows
        for idx, row in enumerate(data_rows):
            # Prepend or overwrite the No. field
            # In the user's case, row is 30 elements, where row[0] is empty batch_id
            if len(row) < len(HEADERS_VENDOR):
                # pad row with empty strings
                row += [""] * (len(HEADERS_VENDOR) - len(row))
                
            # Create a new list mapped to correct columns
            new_row = list(row)
            
            # Since Column A was empty batch_id, we shift batch_id to index 1 (Column B)
            # and set index 0 (Column A) as No.
            new_row[0] = idx + 1 # No. (1, 2, 3...)
            new_row[1] = "GV-AGENT-20260804-01" # Batch ID
            new_row[28] = "2026-08-04" # Research Date
            formatted_rows.append(new_row)
    
    # Overwrite the sheet with headers + formatted rows
    wks_vendor.clear()
    all_vendor_data = [HEADERS_VENDOR] + formatted_rows
    wks_vendor.update("A1", all_vendor_data)
    print(f"Successfully wrote {len(all_vendor_data)} rows to {vendor_sheet_name}.")
    
    # --- 2. Batch Log sheet ---
    print(f"\n2. Initializing '{batch_log_sheet_name}'...")
    wks_batch = sh.worksheet(batch_log_sheet_name)
    existing_batch = wks_batch.get_all_values()
    
    batch_rows = []
    if len(existing_batch) > 0 and len(existing_batch[0]) > 0:
        if existing_batch[0][0] == "No.":
            batch_rows = [r for r in existing_batch[1:] if len(r) > 0 and any(r)]
        else:
            # Shift data for No. column
            valid_existing = [r for r in existing_batch if len(r) > 0 and any(r)]
            for idx, r in enumerate(valid_existing):
                new_r = [idx + 1] + r
                batch_rows.append(new_r)
                
    wks_batch.clear()
    all_batch_data = [HEADERS_BATCH] + batch_rows
    wks_batch.update("A1", all_batch_data)
    print(f"Successfully wrote {len(all_batch_data)} rows to {batch_log_sheet_name}.")
    
    # --- 3. Error Log sheet ---
    print(f"\n3. Initializing '{error_log_sheet_name}'...")
    wks_error = sh.worksheet(error_log_sheet_name)
    existing_error = wks_error.get_all_values()
    
    error_rows = []
    if len(existing_error) > 0 and len(existing_error[0]) > 0:
        if existing_error[0][0] == "No.":
            error_rows = [r for r in existing_error[1:] if len(r) > 0 and any(r)]
        else:
            valid_existing = [r for r in existing_error if len(r) > 0 and any(r)]
            for idx, r in enumerate(valid_existing):
                new_r = [idx + 1] + r
                error_rows.append(new_r)
                
    wks_error.clear()
    all_error_data = [HEADERS_ERROR] + error_rows
    wks_error.update("A1", all_error_data)
    print(f"Successfully wrote {len(all_error_data)} rows to {error_log_sheet_name}.")
    
    print("\nInitialization Complete!")

if __name__ == "__main__":
    initialize_sheets()
