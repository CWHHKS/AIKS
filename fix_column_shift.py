import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
vendor_sheet_name = os.getenv("VENDOR_SHEET_NAME", "01_Vendor_Candidates")

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
key_path = os.path.join(os.getcwd(), "service_account.json")

creds = Credentials.from_service_account_file(key_path, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(spreadsheet_id)

def fix_data_alignment():
    wks = sh.worksheet(vendor_sheet_name)
    rows = wks.get_all_values()
    
    if len(rows) <= 1:
        print("No data rows to align.")
        return
        
    headers = rows[0]
    data_rows = rows[1:]
    
    new_data_rows = []
    
    for idx, r in enumerate(data_rows):
        # We know that the columns are shifted because:
        # - Primary AI Category (Index 7, Column H) contains "Enterprise Automation | Developer Tools" (which is actually secondary tags)
        # - Secondary AI Categories (Index 8, Column I) contains the Company Summary ("CrewAI provides...")
        # - Company Summary (Index 9, Column J) contains Target Customers ("Software developers...")
        # - and so on.
        
        # Let's realign them:
        new_row = list(r)
        
        # 1. Store the shifted values
        primary_val = r[7] # e.g. "Enterprise Automation | Developer Tools"
        summary_val = r[8] # e.g. "CrewAI provides..."
        customers_val = r[9] # e.g. "Software developers..."
        industries_val = r[10] # e.g. "General Enterprise"
        use_cases_val = r[11] # e.g. "Multi-agent..."
        deployment_val = r[12] # e.g. "Cloud (SaaS)..."
        prod_page_val = r[13] # e.g. "https://www.crewai.com/enterprise"
        about_page_val = r[14]
        contact_page_val = r[15]
        korea_presence_val = r[16]
        partner_type_val = r[17]
        relevance_val = r[18]
        b2b_val = r[19]
        proprietary_val = r[20]
        score_val = r[21]
        rec_val = r[22]
        evidence_val = r[23]
        sources_val = r[24] if len(r) > 24 else ""
        review_status = r[25] if len(r) > 25 else "New"
        processing_status = r[26] if len(r) > 26 else "Completed"
        research_date = r[27] if len(r) > 27 else "2026-08-04"
        error_msg = r[28] if len(r) > 28 else ""
        research_notes = r[29] if len(r) > 29 else ""
        
        # 2. Re-assign correctly
        new_row[7] = "AI Agents" # Primary Category (since this batch is AI Agents)
        new_row[8] = primary_val # Secondary Categories (e.g. "Enterprise Automation | Developer Tools")
        new_row[9] = summary_val # Company Summary
        new_row[10] = customers_val # Target Customers
        new_row[11] = industries_val # Target Industries
        new_row[12] = use_cases_val # Main Use Cases
        new_row[13] = deployment_val # Deployment Type
        new_row[14] = prod_page_val # Official Product Page
        new_row[15] = about_page_val # Official About Page
        new_row[16] = contact_page_val # Official Contact Page
        new_row[17] = korea_presence_val # Korea Presence Found
        new_row[18] = partner_type_val # Potential Partner Type
        new_row[19] = relevance_val # Korea Market Relevance
        new_row[20] = b2b_val # B2B Product Confirmed
        new_row[21] = proprietary_val # Proprietary Product Confirmed
        new_row[22] = score_val # Confidence Score
        new_row[23] = rec_val # AIKA Recommendation
        new_row[24] = evidence_val # Primary Evidence URL
        
        # Ensure list is padded to 31 elements
        if len(new_row) < 31:
            new_row += [""] * (31 - len(new_row))
            
        new_row[25] = sources_val # Additional Source URLs
        new_row[26] = review_status
        new_row[27] = processing_status
        new_row[28] = research_date
        new_row[29] = error_msg
        new_row[30] = research_notes
        
        new_data_rows.append(new_row)
        
    # Write back to sheet starting from row 2
    wks.update("A2", new_data_rows)
    print("Re-alignment complete for all 5 rows!")

if __name__ == "__main__":
    fix_data_alignment()
