import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from services.gemini_client import GeminiClient
import google.generativeai as genai

load_dotenv()

print("Loading cached discovery report...")
with open("data/local_backup/test_discovery_report.txt", "r", encoding="utf-8") as f:
    report = f.read()

# Split the report
sections = re.split(r'---+\s*(?=### Candidate)', report)
if len(sections) <= 1:
    sections = re.split(r'(?=### Candidate)', report)

cleaned_sections = []
for sec in sections:
    sec_str = sec.strip()
    if "Company Name" in sec_str or "company_name" in sec_str.lower():
        cleaned_sections.append(sec_str)

print(f"Successfully split report into {len(cleaned_sections)} candidate sections.")

# Test structuring a single candidate
client = GeminiClient()
client.structure_model_name = "models/gemini-3.5-flash"  # Flash is fast and cheap!

single_candidate_template = """Convert the supplied single AIKA vendor research result section into a valid JSON object.
Use only information contained in the supplied section.
Do not perform new web searches.
Do not add, infer, or invent information.
Do not include explanations outside the JSON.

Use this JSON structure:
{
  "company_name": "string",
  "official_website": "string",
  "normalized_domain": "string",
  "headquarters_country": "string or null",
  "main_ai_product": "string or null",
  "primary_ai_category": "allowed category",
  "secondary_ai_categories": [],
  "company_summary": "string",
  "target_customers": [],
  "target_industries": [],
  "main_use_cases": [],
  "deployment_type": [],
  "official_product_page": "string or null",
  "official_about_page": "string or null",
  "official_contact_page": "string or null",
  "korea_presence_found": "Yes | No evidence found | Review Required",
  "potential_korean_partner_type": [],
  "korea_market_relevance": "string",
  "b2b_product_confirmed": "Yes | No | Not publicly confirmed",
  "proprietary_product_confirmed": "Yes | No | Not publicly confirmed",
  "confidence_score": 0,
  "aika_recommendation": "Strong Candidate | Candidate",
  "primary_evidence_url": "string",
  "additional_source_urls": [],
  "review_status": "New",
  "processing_status": "Completed",
  "research_notes": "string or null"
}

Separate multiple values as JSON arrays.
Use null for unavailable single-value fields.
Use an empty array for unavailable multiple-value fields.

CRITICAL FORMATTING FOR SPREADSHEETS:
For "company_summary" and "korea_market_relevance", format the text with logical line breaks (using \\n) to separate key points into short, highly readable paragraphs (e.g. max 2-3 sentences per paragraph, or bullet points separated by \\n). This is required for visual formatting in sheets.
"""

print("\nStructuring Candidate 1...")
user_prompt = f"{single_candidate_template}\n\nRESEARCH REPORT SECTION TO STRUCTURE:\n{cleaned_sections[0]}"

model = genai.GenerativeModel(model_name=client.structure_model_name)
response = model.generate_content(
    user_prompt,
    generation_config={
        "response_mime_type": "application/json"
    }
)

print("Parsed response:")
try:
    data = json.loads(response.text)
    print(json.dumps(data, indent=2))
    print("SUCCESS!")
except Exception as e:
    print("FAILED to parse:", e)
    print("Raw text:", response.text)
