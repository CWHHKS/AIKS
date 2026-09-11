import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("DISCOVERY_MODEL", "gemini-3.5-flash")

genai.configure(api_key=api_key)

# Test 1: google_search_retrieval
print("--- Test: google_search_retrieval ---")
try:
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=[{"google_search_retrieval": {}}]
    )
    print("Model initialized. Generating content...")
    response = model.generate_content("Find the official website of OpenAI and what they do.")
    print("SUCCESS!")
    print(f"Response: {response.text[:200]}...")
except Exception as e:
    print("FAILED!")
    print(f"Error: {e}")

# Test 2: google_search_retrieval with dynamic config
print("\n--- Test: google_search_retrieval with dynamic config ---")
try:
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=[{
            "google_search_retrieval": {
                "dynamic_retrieval_config": {
                    "mode": "MODE_DYNAMIC",
                    "dynamic_threshold": 0.3
                }
            }
        }]
    )
    print("Model initialized. Generating content...")
    response = model.generate_content("Find the official website of OpenAI and what they do.")
    print("SUCCESS!")
    print(f"Response: {response.text[:200]}...")
except Exception as e:
    print("FAILED!")
    print(f"Error: {e}")
