import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import re
import google.generativeai as genai
import google.ai.generativelanguage_v1beta as glm
import requests
from services.audit_agent import GPTNewsAuditor
from services.sheets_client import SheetsClient

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
search_tool = glm.Tool(google_search={})
model = genai.GenerativeModel(model_name="gemini-2.5-flash", tools=[search_tool])

prompt = """Find the exact direct working URL of the news article for:
Title: "Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B"
Event: Ilya Sutskever's startup Safe Superintelligence (SSI) raises $1 billion in funding on September 4, 2024.

Requirements:
- Find a working direct article URL on TechCrunch, Reuters, ZDNet, ETNews, or Naver News.
- Do NOT return a search query link.
- Return ONLY the exact article URL starting with https://.
"""

resp = model.generate_content(prompt)
print("Gemini Response:\n", resp.text, flush=True)

urls = re.findall(r'https?://[^\s\)]+', resp.text)
headline_title = "Safe Superintelligence, co-founded by OpenAI's former chief scientist, raises $1B"
auditor = GPTNewsAuditor()

verified_url = None
for u in urls:
    clean_u = u.rstrip(".,;\"'")
    print(f"\nAuditing URL: {clean_u}", flush=True)
    try:
        r = requests.get(clean_u, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
        print(f" Status: {r.status_code}", flush=True)
        if r.status_code == 200:
            r.encoding = r.apparent_encoding or 'utf-8'
            cleaned_html = re.sub(r'<script[^>]*>.*?</script>', ' ', r.text, flags=re.DOTALL | re.IGNORECASE)
            cleaned_html = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<[^>]+>', ' ', cleaned_html)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            res = auditor.audit_news_page(headline_title, "TechCrunch", clean_text)
            print(f" Approved: {res.get('approved')}, Reason: {res.get('reason')}", flush=True)
            if res.get('approved'):
                verified_url = clean_u
                print(f"\n SUCCESS! Found 100% Verified Link for Item 15:\n {verified_url}", flush=True)
                break
    except Exception as e:
        print(f" Exception: {e}", flush=True)

if verified_url:
    sheets = SheetsClient()
    ws = sheets.news_spreadsheet.worksheet("06_News_All")
    ws.update_cell(16, 7, verified_url)
    print("Updated Google Sheet Row 16 Cell G16 with verified URL!", flush=True)
