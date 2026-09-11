import os
from dotenv import load_dotenv
import google.generativeai as genai
import google.ai.generativelanguage as glm

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("DISCOVERY_MODEL", "gemini-3.5-flash")

genai.configure(api_key=api_key)

print("--- Test: glm.Tool(google_search=glm.GoogleSearch()) ---")
try:
    # Construct Google Search tool directly using protobuf Tool class
    search_tool = glm.Tool(google_search=glm.GoogleSearch())
    
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=[search_tool]
    )
    print("Model initialized. Generating content...")
    response = model.generate_content("Find the official website of OpenAI and what they do.")
    print("SUCCESS!")
    print(f"Response: {response.text[:200]}...")
except Exception as e:
    print("FAILED!")
    print(f"Error: {e}")
