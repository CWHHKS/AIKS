import os
import gspread
from google.oauth2.service_account import Credentials

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
key_path = os.path.join(os.getcwd(), "service_account.json")

# Candidate 1: with lowercase L (4lj)
id_l = "1QQvokAW3wErA0qCDNY4ljGZNQRHpT7s10VeRbC-PuO4"
# Candidate 2: with uppercase I (4Ij)
id_i = "1QQvokAW3wErA0qCDNY4IjGZNQRHpT7s10VeRbC-PuO4"
# Candidate 3: maybe another character? 

creds = Credentials.from_service_account_file(key_path, scopes=scopes)
gc = gspread.authorize(creds)

for name, sheet_id in [("Lowercase L (4lj)", id_l), ("Uppercase I (4Ij)", id_i)]:
    print(f"Testing ID {name}: {sheet_id}")
    try:
        sh = gc.open_by_key(sheet_id)
        print(f"SUCCESS! Accessible Sheet Title: {sh.title}")
    except Exception as e:
        print(f"FAILED: {e}")
