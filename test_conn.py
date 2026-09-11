import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("DISCOVERY_MODEL", "gemini-3.5-flash")

print(f"API Key: {api_key[:10]}... if api_key else 'None'")
print(f"Model: {model_name}")

if not api_key:
    print("Error: GEMINI_API_KEY not found in environment.")
    exit(1)

genai.configure(api_key=api_key)

try:
    print("Testing connection with light generate_content...")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("hello")
    print("SUCCESS!")
    print(f"Response: {response.text}")
except Exception as e:
    print("FAILED!")
    print(f"Error Type: {type(e)}")
    print(f"Error Details: {str(e)}")
