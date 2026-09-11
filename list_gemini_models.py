import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print("API Key:", api_key[:10] + "..." if api_key else "None")

genai.configure(api_key=api_key)

try:
    models = genai.list_models()
    print("\nAvailable models:")
    for m in models:
        print(f"  - {m.name} (supports: {m.supported_generation_methods})")
except Exception as e:
    print("Error listing models:", e)
