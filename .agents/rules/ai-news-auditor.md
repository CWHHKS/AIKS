# AI News Auditor & Failover System Rules

When performing AI news discovery, URL verification, or automated news digests for AIKA:

1. **Dual-LLM Failover Enforcement**:
   - Primary news collector MUST use Gemini Flash with Google Search Grounding (`services/gemini_client.py`).
   - If Gemini API fails with 429 quota, 503, or timeouts, automatically failover to OpenAI `gpt-4o-mini` (`_fallback_openai_discovery`). Resume Gemini on recovery.

2. **GPT Auditor Agent Cross-Verification (`GPTNewsAuditor`)**:
   - Every collected news article MUST be audited via `services/audit_agent.py` using `gpt-4o-mini`.
   - Reject pages with `page_type: PRODUCT_LANDING` (e.g. `paloaltonetworks.com/prisma-airs`) or `HOMEPAGE`.
   - Enforce `fact_match: true` before granting `approved: true`.

3. **URL Resolution & Integrity (`url_resolver.py`)**:
   - Verify path depth (reject root domains and language roots `/ko`).
   - Test HTTP GET status code 200 OK.
   - Filter soft 404s ("Stop the Presses!").
   - **STRICT DIRECT URL RULE**: Search query URLs (e.g., `google.com/search?q=...`) are **STRICTLY DISALLOWED** as final URLs. Final URLs must be the actual direct article deep-link on the news media domain (e.g. `techcrunch.com/...`, `zdnet.co.kr/...`).
