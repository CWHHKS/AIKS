---
name: ai-news-auditor-collector
description: >-
  Multi-Agent AI news collection, Dual-LLM failover (Gemini 2.5/3.5 Flash -> GPT-4o-mini),
  deep-link URL resolution, 3-stage strict cross-verification, and multi-outlet URL priority rules for AIKA.
---

# AI News Auditor & Dual-LLM Collector Skill

## Overview
This skill defines the multi-agent execution pipeline for AIKA (AI Korea Access) news discovery, URL verification, 3-stage semantic auditing, multi-outlet duplicate resolution, and automated digest email dispatch.

## Multi-Agent Architecture & Roles

### 1. Primary Collector Agent (`GeminiClient`)
- **Engine**: Gemini 2.5/3.5 Flash with Google Search Grounding (`services/gemini_client.py`).
- **Function**: Performs real-time web search for high-impact AI technology and business news, generates 1-2 sentence Korean summaries and structured 10-line bullet point breakdowns.

### 2. Fallback Collector Agent (`gpt-astra`)
- **Engine**: OpenAI `gpt-astra` API (`services/gemini_client.py` - `_fallback_openai_discovery`).
- **Function**: Standby collection agent. Automatically takes over when Gemini returns HTTP 429 (quota), 503, or connection timeouts. Self-heals back to Gemini when recovered.

### 3. Deep-Link URL Resolver & 3-Stage Cross-Verification (`url_resolver.py`)
- **Engine**: HTTP GET inspector, WAF sanitizer & Entity Pre-filter (`services/url_resolver.py`).
- **Function**:
  - **Stage 1 (HTTP 200 & WAF Block Filter)**: Validates path depth, tests live 200 OK status, auto-decodes EUC-KR/CP949/UTF-8 charsets, and filters WAF security blocks ("Web firewall security policies") & Soft 404s.
  - **Stage 2 (Keyword Entity Pre-filter)**: Extracts proper nouns, company names, and product names from headline. Rejects articles with 0 matching headline entities in body text.
  - **Stage 3 (GPT Auditor Agent Deep Match)**: Sends cleaned text to `GPTNewsAuditor` for semantic topic matching.
  - **STRICT DIRECT URL REQUIREMENT**: The URL MUST BE the exact direct article page URL on the target news site (e.g. `https://aitimes.kr/...`, `https://zdnet.co.kr/...`). Search query result URLs (`google.com/search?q=...`) are **STRICTLY PROHIBITED** as final URLs.

### 4. Multi-Outlet Coverage & Duplicate Resolution Rules (동일 기사 다중 보도 시 URL 선정 기준)
When a press release or news event is covered by multiple news media outlets simultaneously, apply the following URL selection priority hierarchy:

1. **Priority 1: Target Media Outlet Match (지정/요청 언론사 우선)**
   - If the spreadsheet column `언론사/출처` or user specifies a target outlet (e.g. `인공지능신문`, `전자신문`, `ZDNet Korea`), use the verified direct URL from that specific media outlet.
2. **Priority 2: Primary Tech Press Direct Link (IT/AI 전문지 우선)**
   - Prioritize specialized AI & IT news media:
     - `인공지능신문 (aitimes.kr)` / `ZDNet Korea (zdnet.co.kr)` / `전자신문 (etnews.com)` / `디지털데일리 (ddaily.co.kr)` / `블로터 (bloter.net)`
3. **Priority 3: Major Business & News Dailies (주요 일간지/경제지)**
   - Secondary coverage from national news agencies and business press:
     - `연합뉴스 (yna.co.kr)` / `조선비즈 (biz.chosun.com)` / `한국경제 (hankyung.com)` / `매일경제 (mk.co.kr)`
4. **Priority 4: Stable Portal News Deep-Link Fallback (네이버 뉴스 보존 링크)**
   - If a direct newspaper URL returns a WAF block message or soft 404, fallback to the official Naver News deep-link (`https://n.news.naver.com/mnews/article/...`), which provides 100% stable HTTP 200 OK access to press release articles.

### 5. Independent Auditor Agent (`GPTNewsAuditor`)
- **Engine**: OpenAI `gpt-astra` (`services/audit_agent.py`).
- **Function**: Conducts deep 3-tier cross-verification on extracted page text against headline title & media:
  1. **Page Type Classification (`page_type`)**: Must be `NEWS_ARTICLE` or `PRESS_RELEASE`. Rejects `PRODUCT_LANDING` or `HOMEPAGE`.
  2. **Semantic Fact Matching (`fact_match`)**: Confirms presence of headline entities, funding amounts ($60M, Series B), or core events.
  3. **Approval Verdict (`approved`)**: Returns `true` ONLY if page_type is valid AND fact_match is true.

### 6. Daily Mailer & Sheets Sync Agent (`daily_news_mailer.py`)
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

### 3. Test 3-Stage Cross-Verification
```bash
.\.venv\Scripts\python.exe scratch/test_pipeline_upgrade.py
```

---

## Configuration (`.env`)
- `GEMINI_API_KEY`: Primary Gemini Grounding key.
- `OPENAI_API_KEY`: Fallback collector & GPT Auditor key (`sk-proj-...`).
- `GPT_AUDIT_MODEL`: `gpt-astra`.
- `NEWS_SHEET_NAME`: `06_News_All`.
