import os
import gspread
from google.oauth2.service_account import Credentials

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
key_path = os.path.join(os.getcwd(), "service_account.json")

creds = Credentials.from_service_account_file(key_path, scopes=scopes)
gc = gspread.authorize(creds)

try:
    print("Listing all spreadsheets shared with this service account:")
    sheets = gc.openall()
    if not sheets:
        print("No spreadsheets found! This means the service account does not see any shared sheets yet.")
    for sh in sheets:
        print(f"- Title: '{sh.title}', ID: '{sh.id}'")
except Exception as e:
    print(f"Error: {e}")
