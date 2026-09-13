---
name: ai-news-auditor-collector
description: >-
  Multi-Agent AI news collection, Dual-LLM failover (Gemini 2.5/3.5 Flash -> GPT-4o-mini),
  deep-link URL resolution, and 2-tier GPT Auditor Agent cross-verification for AIKA.
---

# AI News Auditor & Dual-LLM Collector Skill

## Overview
This skill defines the multi-agent execution pipeline for AIKA (AI Korea Access) news discovery, URL verification, semantic auditing, and automated digest email dispatch.

## Multi-Agent Architecture & Roles

### 1. Primary Collector Agent (`GeminiClient`)
- **Engine**: Gemini 2.5/3.5 Flash with Google Search Grounding (`services/gemini_client.py`).
- **Function**: Performs real-time web search for high-impact AI technology and business news, generates 1-2 sentence Korean summaries and structured 10-line bullet point breakdowns.

### 2. Fallback Collector Agent (`GPT-4o-mini`)
- **Engine**: OpenAI `gpt-4o-mini` API (`services/gemini_client.py` - `_fallback_openai_discovery`).
- **Function**: Standby collection agent. Automatically takes over when Gemini returns HTTP 429 (quota), 503, or connection timeouts. Self-heals back to Gemini when recovered.

### 3. Deep-Link URL Resolver Agent (`url_resolver.py`)
- **Engine**: HTTP GET inspector & URL sanitizer (`services/url_resolver.py`).
- **Function**:
  - Validates path depth (rejects root domains like `paloaltonetworks.com` or language roots `/ko`).
  - Executes live HTTP GET to ensure 200 OK status.
  - Filters out Soft 404 error messages ("Stop the Presses!", "Page not found").
  - **CRITICAL DIRECT URL REQUIREMENT**: The URL MUST BE the exact direct article page URL on the target news site (e.g. `https://techcrunch.com/...`, `https://zdnet.co.kr/...`). Search query result URLs (`google.com/search?q=...`) are **STRICTLY PROHIBITED** as final URLs.

### 4. Independent Auditor Agent (`GPTNewsAuditor`)
- **Engine**: OpenAI `gpt-4o-mini` (`services/audit_agent.py`).
- **Function**: Conducts 2-tier cross-verification on extracted page text against headline title & media:
  1. **Page Type Classification (`page_type`)**: Must be `NEWS_ARTICLE` or `PRESS_RELEASE`. Rejects `PRODUCT_LANDING` or `HOMEPAGE`.
  2. **Semantic Fact Matching (`fact_match`)**: Confirms presence of headline entities, funding amounts ($60M, Series B), or core events.
  3. **Approval Verdict (`approved`)**: Returns `true` ONLY if page_type is valid AND fact_match is true.

### 5. Daily Mailer & Sheets Sync Agent (`daily_news_mailer.py`)
- **Engine**: Schedule manager & Sheets integrator (`daily_news_mailer.py`).
- **Function**: Manages 18:00 KST evening buffering, 06:00 KST morning digest email dispatch, and syncs verified articles to Google Sheet `06_News_All`.

---

## Execution Commands

### 1. Run Evening News Collection (18:00 KST Buffer)
```bash
.\.venv\Scripts\python.exe daily_news_mailer.py --action collect_evening --count 5
```

### 2. Run Morning Digest & Email Dispatch (06:00 KST)
```bash
.\.venv\Scripts\python.exe daily_news_mailer.py --action collect_and_send --count 5 --to changwan.lim@agichang.ai
```

### 3. Test GPT Auditor Cross-Verification
```bash
.\.venv\Scripts\python.exe -c "from services.audit_agent import GPTNewsAuditor; a = GPTNewsAuditor(); print(a.audit_news_page('Title', 'Media', 'Page text'))"
```

### 4. Test Full Pipeline Verification
```bash
.\.venv\Scripts\python.exe scratch/verify_all_features.py
```

---

## Configuration (`.env`)
- `GEMINI_API_KEY`: Primary Gemini Grounding key.
- `OPENAI_API_KEY`: Fallback collector & GPT Auditor key (`sk-proj-...`).
- `GPT_AUDIT_MODEL`: `gpt-4o-mini` (fast, cost-effective).
- `NEWS_SHEET_NAME`: `06_News_All`.
