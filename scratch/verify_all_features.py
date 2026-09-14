import os
import sys
import logging
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyFeatures")

def test_gpt_auditor():
    print("\n--- 1. Testing GPT Auditor Agent Cross-Verification ---")
    from services.audit_agent import GPTNewsAuditor
    auditor = GPTNewsAuditor()
    print("Is GPT Auditor Available?", auditor.is_available())
    
    # Test valid news text
    valid_text = """
    SAN FRANCISCO - Protect AI today announced it has raised $60 million in Series B funding led by Evolution Equity Partners.
    The company builds cybersecurity solutions specifically tailored for machine learning models and artificial intelligence applications.
    """
    res1 = auditor.audit_news_page("Protect AI Raises $60M Series B Funding", "TechCrunch", valid_text)
    print("Valid News Audit Result:", res1)
    assert res1.get("approved") == True, "Valid news should be approved!"

    # Test product landing page text
    landing_text = """
    Welcome to Palo Alto Networks Prisma AIRS. Protect your enterprise AI applications with automated AI posture management.
    Contact sales today for a demo or start your free trial.
    """
    res2 = auditor.audit_news_page("Palo Alto Networks Prisma AIRS", "Palo Alto Networks", landing_text)
    print("Landing Page Audit Result:", res2)
    assert res2.get("approved") == False, "Product landing page should be REJECTED!"
    print("[OK] GPT Auditor Agent Cross-Verification Passed!")

def test_dual_llm_failover():
    print("\n--- 2. Testing Dual-LLM Failover System ---")
    from services.gemini_client import GeminiClient
    client = GeminiClient()
    
    # Test fallback discovery directly
    prompt = "Find 1 recent AI news article headline and source."
    sys_prompt = "You are an AI news collector."
    fallback_report = client._fallback_openai_discovery(prompt, sys_prompt)
    print("Fallback GPT-4o-mini Discovery Output Sample:", fallback_report[:150])
    assert len(fallback_report) > 0, "Fallback discovery output should not be empty!"
    print("[OK] Dual-LLM Failover System Passed!")

if __name__ == "__main__":
    test_gpt_auditor()
    test_dual_llm_failover()
