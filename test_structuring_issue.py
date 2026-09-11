import os
import json
from datetime import datetime
from dotenv import load_dotenv
from services.gemini_client import GeminiClient

load_dotenv()

print("Initializing Gemini Client...")
client = GeminiClient()
client.discovery_model_name = "models/gemini-3.5-flash"
client.structure_model_name = "models/gemini-2.5-pro"

batch_params = {
    "batch_id": "GV-ALL-TEST-01",
    "region": "Global",
    "category": "All",
    "industries": "General Enterprise",
    "minimum_confidence_score": 70,
    "exclude_hyperscalers": True,
    "korea_presence_policy": "포함하되 표시",
    "research_date": datetime.now().strftime("%Y-%m-%d"),
    "preferred_sources": "ycombinator.com, crunchbase.com, producthunt.com, techcrunch.com",
    "target_count": 10
}

existing_domains = []

print("\nRunning Stage 1: Discovery (Searching for 10 candidates)...")
try:
    report = client.run_discovery_stage(batch_params, existing_domains)
    print("Stage 1 SUCCESS! Report length:", len(report))
    
    # Save discovery report for inspection
    with open("data/local_backup/test_discovery_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print("Saved discovery report to data/local_backup/test_discovery_report.txt")
    
except Exception as e:
    print("Stage 1 FAILED:", e)
    exit(1)

print("\nRunning Stage 2: Structuring...")
try:
    structured = client.run_structuring_stage("GV-ALL-TEST-01", report, target_count=10)
    print("Stage 2 SUCCESS!")
    print(f"Parsed {len(structured.get('candidates', []))} candidates.")
except Exception as e:
    print("Stage 2 FAILED:", e)
    # If it failed, let's write a script to inspect why or print the raw response if possible
    # We can write a custom call here to get the raw response to debug
    import google.generativeai as genai
    model = genai.GenerativeModel(model_name=client.structure_model_name)
    user_prompt = f"{client.structure_prompt_template.replace('{target_count}', '10')}\n\nRESEARCH REPORT TO STRUCTURE:\n{report}"
    
    print("\nRe-generating raw response for debugging...")
    response = model.generate_content(
        user_prompt,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 8192
        }
    )
    print("Raw Response Text:")
    print("-" * 50)
    print(response.text)
    print("-" * 50)
    
    # Write raw response to debug file
    with open("data/local_backup/raw_structure_response.json", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Saved raw response to data/local_backup/raw_structure_response.json")
