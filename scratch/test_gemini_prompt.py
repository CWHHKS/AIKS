import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import re
import google.generativeai as genai
import google.ai.generativelanguage_v1beta as glm
from services.audit_agent import GPTNewsAuditor
from services.url_resolver import is_valid_deep_link

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
search_tool = glm.Tool(google_search={})
model = genai.GenerativeModel(model_name="gemini-2.5-flash", tools=[search_tool])

prompt = """Find the exact direct news article URL published by ETNews (전자신문) or ZDNet Korea on May 2, 2024 for:
Title: "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시" (or 삼성SDS 패브릭스 브리티 출시)

Requirements:
- Must be a direct article URL on etnews.com or zdnet.co.kr or news.naver.com.
- Do NOT return a search query or search engine link.
- Return the direct URL.
"""

resp = model.generate_content(prompt)
print("Gemini Response:\n", resp.text)

urls = re.findall(r'https?://[^\s\)]+', resp.text)
title = "삼성SDS, 생성형 AI 서비스 '패브릭스·브리티' 출시"
media = "전자신문"

for u in urls:
    u_clean = u.rstrip(".,;\"'")
    print(f"\nAuditing URL: {u_clean}")
    valid = is_valid_deep_link(u_clean, title=title, media=media)
    print(f"Is valid: {valid}")
