# AI News Auditor & Failover System Rules

When performing AI news discovery, URL verification, or automated news digests for AIKA:

1. **Dual-LLM Failover Enforcement**:
   - Primary news collector MUST use Gemini Flash with Google Search Grounding (`services/gemini_client.py`).
   - If Gemini API fails with 429 quota, 503, or timeouts, automatically failover to OpenAI `gpt-astra` (`_fallback_openai_discovery`). Resume Gemini on recovery.

2. **3-Stage Strict Cross-Verification Pipeline (`url_resolver.py` & `audit_agent.py`)**:
   - **Stage 1 (HTTP 200 & Structural/WAF Filter)**: Verify path depth, test HTTP GET status code 200 OK, decode charset (EUC-KR/CP949/UTF-8), and filter WAF block pages ("web firewall security policies", "blocked request") & soft 404s.
   - **Stage 2 (Entity & Keyword Pre-Filter)**: Extract proper nouns, company names, and product names from the headline. Reject articles where 0 core entities match the article text (e.g. headline is about Samsung SDS AI, but body is about EV batteries).
   - **Stage 3 (GPT Auditor Agent Deep Semantic Audit)**: Run `GPTNewsAuditor` (`gpt-astra`) on cleaned body text. Reject product landings, homepages, and mismatched topics (`approved: false`).

3. **Strict Recency Mandate (최신성 강제 수집 규칙)**:
   - All collected articles MUST be published in the **CURRENT YEAR / RECENT 30 DAYS** relative to execution date.
   - REJECT and filter out historical news articles from previous years (e.g. 2024 or 2025).
   - Explicitly append current year filters (e.g. `2026` / recent weeks) to Google Search queries during discovery.

4. **Multi-Outlet URL Selection Priority Rules (동일 기사 다중 보도 시 URL 선정 기준)**:
   - **우선순위 1 (지정 언론사 매칭)**: 시트의 `언론사/출처` 컬럼이나 사용자가 지정한 특정 언론사(예: `인공지능신문`, `전자신문`, `ZDNet Korea`)의 검증된 직링크 URL을 최우선 적용.
   - **우선순위 2 (IT/AI 전문 매체 직링크)**: 지정 언론사가 없거나 접속 불가 시 IT/AI 전문 매체(`aitimes.kr`, `zdnet.co.kr`, `etnews.com`, `ddaily.co.kr`, `bloter.net`) URL 선정.
   - **우선순위 3 (주요 종합지/경제지)**: `yna.co.kr`, `biz.chosun.com`, `hankyung.com` 등 주요 언론사 URL.
   - **우선순위 4 (네이버 뉴스 포털 보존 링크)**: 언론사 본사 직링크가 방화벽(WAF) 차단 또는 404 오류 시 100% 접속 보장되는 네이버 뉴스 포털 다이렉트 링크(`n.news.naver.com/mnews/article/...`) 사용.

5. **URL Resolution & Integrity**:
   - **STRICT DIRECT URL RULE**: Search query URLs (e.g., `google.com/search?q=...`) are **STRICTLY DISALLOWED** as final URLs. Final URLs must be the actual direct article deep-link on the news media domain.
