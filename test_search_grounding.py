import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("DISCOVERY_MODEL", "gemini-3.5-flash")

print(f"API Key: {api_key[:10]}...")
print(f"Model: {model_name}")

genai.configure(api_key=api_key)

# Test 1: with tools="google_search"
print("\n--- Test 1: tools='google_search' ---")
try:
    model = genai.GenerativeModel(
        model_name=model_name,
        tools="google_search"
    )
    print("Model initialized. Generating content...")
    response = model.generate_content("Find the official website of OpenAI and what they do.")
    print("SUCCESS!")
    print(f"Response: {response.text[:200]}...")
    # Check if there are grounding metadata/search results
    if hasattr(response, 'candidates') and response.candidates:
        parts = response.candidates[0].content.parts
        print("Response parts: ", len(parts))
except Exception as e:
    print("FAILED!")
    print(f"Error: {e}")

# Test 2: with tools=[{"google_search": {}}]
print("\n--- Test 2: tools=[{'google_search': {}}] ---")
try:
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=[{"google_search": {}}]
    )
    print("Model initialized. Generating content...")
    response = model.generate_content("Find the official website of OpenAI and what they do.")
    print("SUCCESS!")
    print(f"Response: {response.text[:200]}...")
except Exception as e:
    print("FAILED!")
    print(f"Error: {e}")
