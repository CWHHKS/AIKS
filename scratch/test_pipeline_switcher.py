import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from services.audit_agent import GPTNewsAuditor

# Test 1: Standard Mode (GPT Auditor)
os.environ["PIPELINE_MODE"] = "standard"
auditor_standard = GPTNewsAuditor()
res_std = auditor_standard.audit_news_page(
    title="삼성SDS 기업용 generative AI 플랫폼 패브릭스 출시",
    media="전자신문",
    page_text="삼성SDS는 2일 서울 송파구 본사에서 기자간담회를 열고 생성형 AI 플랫폼 패브릭스(FabriX)를 출시했다고 밝혔다."
)
print("Standard Mode (GPT Auditor) Result:", res_std)

# Test 2: Reversed Mode (Gemini Auditor)
os.environ["PIPELINE_MODE"] = "reversed"
auditor_reversed = GPTNewsAuditor()
res_rev = auditor_reversed.audit_news_page(
    title="삼성SDS 기업용 generative AI 플랫폼 패브릭스 출시",
    media="전자신문",
    page_text="삼성SDS는 2일 서울 송파구 본사에서 기자간담회를 열고 생성형 AI 플랫폼 패브릭스(FabriX)를 출시했다고 밝혔다."
)
print("Reversed Mode (Gemini Auditor) Result:", res_rev)
