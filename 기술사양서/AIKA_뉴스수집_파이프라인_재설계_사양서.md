# AIKA AI 뉴스 수집 파이프라인 재설계 사양서

| 항목 | 내용 |
|---|---|
| 문서 버전 | v1.0 |
| 작성일 | 2026-09-14 |
| 대상 시스템 | AIKA (aika.agichang.com / Streamlit) |
| 대상 시트 | AI 뉴스 DB (Google Sheets, gid=973581535) |
| 수신자 | 개발 담당자 |

---

## 0. 이 문서의 목적

현재 AIKA 뉴스 수집 파이프라인은 수집된 데이터의 **출처 URL, 기사 게재일이 사실과 다른 값으로 기록되는 문제**를 가지고 있다. 본 문서는 그 원인을 규명하고, 코드 수준에서 무엇을 어떻게 바꿔야 하는지를 정의한다.

기존 시트 115행(2026-08-04 ~ 2026-09-14, 17개 배치)을 전수 분석한 결과를 근거로 한다.

---

## 1. 현상 진단

### 1.1 정량 분석 결과

| 항목 | 수치 |
|---|---|
| 총 기록 행 | 115행 |
| URL 기준 고유 기사 | 91건 (24건 중복 저장) |
| 게재일이 2024년인 기사 | 51건 (56%) |
| 게재일이 2025년인 기사 | 5건 |
| 게재일이 2026년인 기사 | 33건 |
| URL이 실제 기사 주소가 아닌 행 | 25건 (27%) |
| Review Status가 검토 완료인 행 | 0건 |
| 출처 편중 | TechCrunch 36건 + ZDNet Korea 29건 = 전체의 70% |

### 1.2 확인된 3대 결함

#### 결함 A — 출처 URL 위조 (최우선)

수집된 URL의 27%가 해당 기사의 실제 주소가 아니다. 유형별로 분류하면 다음과 같다.

| 유형 | 실제 기록된 값 | 해당 행의 제목 |
|---|---|---|
| 제목 첫 단어로 위키 링크 생성 | `namu.wiki/w/삼성` | 삼성SDS, 생성형 AI 서비스 '패브릭스'에 완전 자율형 AI 에이전트 전격 도입 |
| 동일 패턴 | `namu.wiki/w/금융` | 금융위원회, '금융권 생성형 AI 보안 가이드라인' 확정 |
| 동일 패턴 | `namu.wiki/w/과학` | 과학기술정보통신부, 2027년까지 공공 부문 AI 보안 시스템 고도화 추진 |
| 검색 URL을 출처로 기록 | `google.com/search?q=과기정통부...ZDNet Korea` | 과기정통부, K-클라우드 프로젝트 2단계 착수 |
| 무관한 사이트 | `youtube.com/feed/storefront` | Cognition AI, $800M 유치 |
| 무관한 사이트 | `corporate.jcpenney.com` | Meta releases Llama 3.3 |
| 무관한 사이트 | `r.amazon.co.jp` | Amazon pours another $4B into Anthropic |
| 회사 홈페이지만 기록 | `anthropic.com/`, `openai.com/`, `x.ai/`, `ftc.gov/` | 각 사 제품 출시 기사 |
| URL 날짜와 게재일 불일치 | `zdnet.co.kr/view/?no=20260731...` (게재일 2024-09-02) | 네이버, 글로벌 소버린 AI 동맹 확대 |
| URL 연도와 게재일 불일치 | `techcrunch.com/2025/05/22/...` (게재일 2026-07-15) | Anthropic launches Claude 4 Opus |

**중요**: 이 현상은 대상 사이트의 보안·봇 차단 때문이 아니다. 차단이 원인이라면 결과는 "수집 실패"(빈 값)여야 하며, 형태만 그럴듯한 **다른** URL이 생성되지 않는다.

#### 결함 B — 오래된 기사 유입

수집일이 2026년 8~9월인데 게재일이 2024년인 기사가 51건(56%)이다. 예시:

- EU AI Act 발효 (2024-08-01)
- Anthropic Claude 3.5 Sonnet 출시 (2024-06)
- OpenAI o1-mini 출시 (2024-09)
- Apple Intelligence 출시 (2024-10)

Streamlit 화면의 `기사 게재일 기준(이 날짜 이후 기사만 수집)` 설정값이 2026-08-15임에도 필터링되지 않았다.

#### 결함 C — 비(非)기사 행 저장

2026-09-14 배치(`NEWS-ALL-20260914-AUTO`)에 다음 2개 행이 기사로 저장되어 있다.

- `How to perform the search yourself using Google (구글을 활용한 최신 AI 뉴스 검색 및 분석 가이드)` / 출처 미디어명: `Google Search Guide`
- `Instructions on how to perform AI news search (AI 뉴스 검색 수행 방법에 대한 안내)` / 출처 미디어명: `AIKA AI Research Guide`

수집 에이전트가 검색에 실패했을 때 반환한 안내문이 기사 레코드로 기록되었다.

### 1.3 부차적 결함

- **카테고리 표기 불일치**: `Other`/`Others` 혼용, `Generative AI` 변형 4종(`Generative AI / Large Language Models (LLMs)`, `Generative AI / Open Source LLM`, `Generative AI / SLM (Small Language Model)`), `All`, 공백값 존재
- **Batch ID 형식 3종 혼용**: `NEWS-ALL-YYYYMMDD-NN`, `NEWS-ALL-YYYYMMDD-AUTO`, `NEWS-AUTO-YYYYMMDDHHMM`
- **빈 제목 행 존재**: No.39 (`NEWS-ALL-20260808-AUTO`)
- **수집 공백**: 2026-08-12 → 08-26 → 09-09 사이 각 2주간 수집 없음
- **한국 시장 관련성 변별력 부재**: High 70%, Medium 28% — 사실상 전량 High로 분류
- **중복 제거 미작동**: 동일 URL 24건 중복 저장 (예: 리벨리온-사피온 합병 기사 2회)

---

## 2. 근본 원인

### 2.1 원인 규명

**LLM의 산문 응답 텍스트에서 URL·게재일·제목을 파싱하고 있다.**

Gemini에 Google 그라운딩 검색을 켜더라도, 모델이 **최종 답변 본문에 작성하는 URL은 검색 결과에서 복사된 값이 아니다.** 학습된 패턴에 따라 생성된 문자열이다. "ZDNet Korea 기사이므로 `zdnet.co.kr/view/?no=` + 8자리 숫자" 형태로 형식만 맞춰 출력한다.

게재일도 동일하다. 모델은 학습 데이터에 포함된 2024년 기사를 "AI 뉴스"로 인식하여 반환하며, 프롬프트에 기재된 날짜 조건은 **요청**일 뿐 **필터**가 아니다.

결함 A, B, C는 모두 이 하나의 원인에서 파생된다.

### 2.2 현재 교차검증(GPT-4o)이 무력한 이유

GPT-4o를 Messages API로 호출할 경우 **웹 접근 수단이 없다.** URL이 실존하는지 확인할 방법이 없으므로, 형태가 정상적인 URL은 전부 통과시킨다.

환각으로 생성된 URL은 정의상 "가장 그럴듯한 형태"를 가지므로 통과율이 사실상 100%다. 검증 레이어가 존재하지만 아무것도 걸러내지 못하고 있으며, 실제로 시트에 `Invalid` 판정 행이 0건인 것이 이를 뒷받침한다.

### 2.3 설계 원칙

> **URL, 기사 게재일, 제목, 출처 미디어명 — 이 4개 필드는 어떤 LLM의 출력에서도 가져오지 않는다.**
>
> LLM은 "이미 확보된 본문 텍스트"를 요약·분류하는 역할만 수행한다. 사실 확보는 코드가 담당한다.

---

## 3. 목표 아키텍처

```
[1단계] 발견 (Discovery)          — LLM 미사용
   ├─ RSS 직접 수집 (1순위)
   ├─ Google News RSS (2순위)
   └─ Gemini 그라운딩 (3순위, groundingMetadata만 사용)
              ↓  URL 후보 리스트
[2단계] 검증 (Validation)         — LLM 미사용 ★핵심
   ├─ HTTP 상태 확인
   ├─ 도메인 화이트리스트 대조
   ├─ 게재일 추출 및 컷오프 비교
   └─ canonical URL 기준 중복 제거
              ↓  검증 통과 URL만
[3단계] 본문 확보 (Extraction)    — LLM 미사용
   └─ trafilatura / readability
              ↓  기사 본문 텍스트
[4단계] 요약·분류 (Summarize)     — Gemini
   └─ 본문 내 명시 사실만 사용
              ↓  요약 + 분류 결과
[5단계] 근거 검증 (Grounding)     — Claude + Citations
   └─ 요약 문장별 본문 근거 대조
              ↓
         Google Sheets 기록
```

---

## 4. 단계별 상세 사양

### 4.1 [1단계] 발견 — LLM 미사용

URL 확보는 코드가 수행한다. 3개 채널을 병행하며, 우선순위대로 시도한다.

#### 채널 1 — RSS 직접 수집 (1순위)

현재 화이트리스트에 등록된 매체 대부분이 RSS를 제공한다. 정확도가 가장 높고 비용이 0이다.

| 매체 | RSS 엔드포인트 |
|---|---|
| ZDNet Korea | `https://zdnet.co.kr/news/news_xml.asp` |
| 전자신문 | `https://rss.etnews.com/Section901.xml` (ICT) |
| TechCrunch | `https://techcrunch.com/feed/` |
| VentureBeat | `https://venturebeat.com/feed/` |
| The Verge | `https://www.theverge.com/rss/index.xml` |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` |
| Wired | `https://www.wired.com/feed/rss` |
| AI타임스 | `https://www.aitimes.com/rss/allArticle.xml` |
| 디지털데일리 | `https://www.ddaily.co.kr/rss/allArticle.xml` |

> RSS 주소는 매체 개편 시 변경될 수 있다. 구현 시 각 엔드포인트의 200 응답 및 파싱 가능 여부를 먼저 확인하고, 실패 시 해당 매체는 채널 2로 대체한다. 엔드포인트 목록은 코드에 하드코딩하지 말고 설정 파일(`sources.yaml` 등)로 분리한다.

RSS에서 다음 필드를 그대로 추출한다. **가공하지 않는다.**

- `link` → 출처 URL
- `title` → 제목
- `pubDate` → 기사 게재일
- `description` → 본문 확보 실패 시 대체 요약 원문
- 피드 출처 → 출처 미디어명

#### 채널 2 — Google News RSS (2순위)

RSS를 제공하지 않거나 주제별 탐색이 필요한 경우 사용한다.

```
https://news.google.com/rss/search?q={키워드}+when:7d&hl=ko&gl=KR&ceid=KR:ko
```

- `when:7d` 파라미터가 **검색 단계에서** 날짜를 제한한다. 이것이 결함 B의 직접적 해결책이다.
- Streamlit의 `기사 게재일 기준` 설정값을 `when:Nd`로 변환하여 주입한다. (예: 컷오프가 30일 전이면 `when:30d`)
- 반환되는 URL은 `news.google.com` 리다이렉트 형태이므로, **302를 따라가 최종 URL로 해석한 뒤 저장**한다.

#### 채널 3 — Gemini 그라운딩 (3순위)

기존 구현을 유지하되, **읽는 필드를 변경한다.**

| 구분 | 값 |
|---|---|
| 사용해야 할 필드 | `response.candidates[].groundingMetadata.groundingChunks[].web.uri` |
| 사용해야 할 필드 | `response.candidates[].groundingMetadata.groundingChunks[].web.title` |
| **절대 사용 금지** | 응답 본문 텍스트(`candidates[].content.parts[].text`)에 적힌 URL |

`groundingChunks`의 URI는 `vertexaisearch.cloud.google.com/grounding-api-redirect/...` 형태의 리다이렉트이며 **만료 시간이 있다.** 수신 즉시 302를 따라가 최종 URL로 해석하여 저장해야 한다.

> **현재 코드가 `groundingMetadata`를 읽지 않고 응답 텍스트만 파싱하고 있다면, 그 지점이 결함 A의 발생 위치다.** 최우선 확인 대상이다.

#### 1단계 출력

```json
{
  "url": "https://zdnet.co.kr/view/?no=20260812093412",
  "title_raw": "삼성SDS, 생성형 AI 서비스 '패브릭스'에 완전 자율형 AI 에이전트 도입",
  "published_at_raw": "2026-08-12T09:34:00+09:00",
  "source_media_raw": "ZDNet Korea",
  "discovery_channel": "rss",
  "discovered_at": "2026-09-14T10:00:00+09:00"
}
```

---

### 4.2 [2단계] 검증 — LLM 미사용 ★핵심

1단계에서 확보한 각 URL에 대해 아래 검사를 순차 수행한다. **하나라도 실패하면 메인 시트에 기록하지 않는다.**

| 순번 | 검사 항목 | 통과 조건 | 실패 시 처리 |
|---|---|---|---|
| V1 | HTTP 상태 | 최종 응답 200 | `_rejected` 탭, 사유 `HTTP_{코드}` |
| V2 | 최종 도메인 | 화이트리스트 포함 | `_rejected`, 사유 `DOMAIN_NOT_ALLOWED` |
| V3 | 도메인·출처명 일치 | 도메인이 출처 미디어명과 매핑 일치 | `_rejected`, 사유 `SOURCE_MISMATCH` |
| V4 | URL 패턴 | 금지 패턴 미해당 (4.2.1 참조) | `_rejected`, 사유 `INVALID_URL_PATTERN` |
| V5 | 게재일 추출 | 페이지에서 게재일 추출 성공 | `_rejected`, 사유 `NO_PUBLISH_DATE` |
| V6 | 게재일 컷오프 | 설정 컷오프 이후 | `_rejected`, 사유 `TOO_OLD` |
| V7 | 중복 | canonical URL이 기존 시트에 없음 | 스킵, 사유 `DUPLICATE` |

#### 4.2.1 금지 URL 패턴 (V4)

아래에 해당하면 즉시 탈락시킨다. 실제 수집 데이터에서 관찰된 패턴이다.

```python
REJECT_PATTERNS = [
    r'namu\.wiki',                    # 나무위키
    r'google\.com/search',            # 검색 결과 페이지
    r'google\.com/url\?',             # 구글 리다이렉트
    r'youtube\.com',                  # 유튜브
    r'^https?://[^/]+/?$',            # 도메인 루트만 (경로 없음)
    r'/search\?',                     # 일반 검색 쿼리
    r'\.(pdf|zip|jpg|png)$',          # 비(非)기사 파일
]
```

`^https?://[^/]+/?$` 규칙은 `anthropic.com/`, `openai.com/`, `x.ai/`, `ftc.gov/` 같은 홈페이지 루트 URL을 걸러낸다. 기사 URL은 반드시 경로를 가진다.

#### 4.2.2 게재일 추출 우선순위 (V5)

**LLM에게 묻지 않는다.** HTML에서 아래 순서로 탐색한다.

1. `<meta property="article:published_time" content="...">`
2. JSON-LD (`<script type="application/ld+json">`)의 `datePublished`
3. `<meta property="og:published_time">`
4. `<meta name="date">` / `<time datetime="...">`
5. RSS 피드의 `pubDate` (채널 1 경유 시)

1~5 모두 실패하면 V5 탈락. 추출에 사용된 소스를 `게재일 출처` 컬럼에 기록한다.

#### 4.2.3 중복 판정 기준 (V7)

canonical URL로 정규화한 뒤 비교한다.

- `<link rel="canonical">` 값이 있으면 그것을 사용
- 쿼리스트링 중 추적 파라미터(`utm_*`, `fbclid`, `gclid` 등) 제거
- 말미 슬래시 통일, 스킴을 `https`로 통일

동일 기사가 다른 매체에 전재된 경우(예: 연합뉴스 → 각 포털)는 제목 유사도 0.9 이상이면 중복으로 간주하는 2차 판정을 권장한다.

#### 4.2.4 로깅 요구사항

`_rejected` 탭에 탈락 건을 전부 기록한다. 컬럼: `수집일시`, `Batch ID`, `탈락 사유`, `URL`, `제목(원문)`, `발견 채널`.

이 탭은 파이프라인 품질 추적의 유일한 근거가 되므로 **반드시 구현한다.** 현재 시트에 탈락 기록이 0건인 것은 검증이 작동하지 않았음을 의미한다.

---

### 4.3 [3단계] 본문 확보 — LLM 미사용

검증 통과 URL의 기사 본문을 추출한다.

#### 라이브러리

- 1순위: `trafilatura`
- 2순위: `readability-lxml`

#### 요청 헤더 및 매너

```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}
```

- 동일 도메인 연속 요청 간 **1.5~2초 지연**
- 타임아웃 10초, 재시도 1회
- `robots.txt` 준수

#### 차단 대응 매트릭스

실제 봇 차단이 발생하는 것은 이 단계다. 결함 A의 원인은 아니지만 별도로 처리해야 한다.

| 상황 | 처리 |
|---|---|
| 본문 추출 성공 (300자 이상) | 정상 진행 → 4단계 |
| 본문 추출 성공 (300자 미만) | RSS `description`으로 대체 |
| 403 / 봇 차단 | RSS `description`으로 대체 |
| RSS description도 없음 | **행을 버리지 않되, `Review Status = Link-Only`로 기록하고 요약을 생성하지 않는다** |

> **중요**: 본문 없이 요약을 생성하는 것이 현재 환각의 직접 원인이다. 본문이 없으면 `한줄 요약`·`10줄 상세 요약` 컬럼을 **공란으로 둔다.** 제목과 URL만 기록해도 가치가 있으며, 추측으로 채우는 것보다 낫다.

---

### 4.4 [4단계] 요약·분류 — Gemini

#### 입력

- 3단계에서 확보한 **본문 전문**
- 제목, 출처 미디어명 (참고용, 출력 대상 아님)

#### 출력 (이 항목만)

`Primary AI Category`, `News Topic`, `관련 기업명`, `한줄 요약`, `10줄 상세 요약`, `핵심 키워드`, `한국 시장 관련성`, `Research Notes`

**URL, 게재일, 제목, 출처 미디어명은 출력시키지 않는다.** 이 4개는 2단계 결과를 코드가 그대로 기입한다.

#### 프롬프트

```
당신은 AI 산업 뉴스 분석가입니다. 아래 [기사 본문]만을 근거로 분석 결과를 작성하십시오.

절대 규칙:
1. [기사 본문]에 명시되지 않은 사실을 추가하지 마십시오.
2. 본문에서 확인할 수 없는 항목은 "본문 미기재"라고 기재하십시오.
3. URL, 날짜, 제목, 매체명은 출력하지 마십시오.
4. 배경지식으로 알고 있는 내용이라도 본문에 없으면 쓰지 마십시오.
5. 추측, 전망, 일반론을 사실처럼 서술하지 마십시오.

[기사 본문]
{body_text}

[출력 형식] — 아래 JSON만 출력하고 다른 텍스트는 붙이지 마십시오.
{
  "primary_ai_category": "<아래 목록 중 정확히 하나>",
  "news_topic": "<아래 목록 중 정확히 하나>",
  "companies": "<본문에 등장한 기업명만 쉼표로 구분>",
  "one_line_summary": "<100자 내외, 본문 사실만>",
  "detailed_summary": [
    "배경: ...",
    "핵심 사실: ...",
    "기술 스펙: ...",
    "협력 관계: ...",
    "비즈니스 영향: ...",
    "경쟁 구도: ...",
    "한국 시장 영향: ...",
    "SI/MSP 관점: ...",
    "도전 과제: ...",
    "결론: ..."
  ],
  "keywords": "<쉼표 구분 5~7개>",
  "korea_relevance": "High | Medium | Low",
  "korea_relevance_reason": "<한 문장>"
}

primary_ai_category 허용값: {카테고리 목록}
news_topic 허용값: {토픽 목록}
```

#### 카테고리 enum 고정

현재 24종으로 산개한 카테고리를 아래 12종으로 고정한다. 목록 외 값이 오면 `Other`로 강제 변환한다.

```
Generative AI, AI Agents, AI Governance, Data and AI Platform,
AI Security, Conversational AI, Developer Tools, Enterprise Automation,
AI Chips & Hardware, AI Infrastructure, Industry AI, Other
```

News Topic도 동일하게 6종 고정.

```
AI Product Launch, Korea AI Market, Big Tech AI,
AI Policy & Regulation, AI Investment & M&A, AI Industry Trends
```

#### 한국 시장 관련성 판정 기준

현재 High가 70%로 변별력이 없다. 아래 기준을 프롬프트에 명시한다.

| 등급 | 조건 |
|---|---|
| High | 한국 기업·정부기관이 주체이거나, 한국 시장에 직접 규제·공급 영향이 있는 경우 |
| Medium | 글로벌 사안이나 한국 기업이 도입·대응해야 할 기술·정책인 경우 |
| Low | 해외 시장 내부 사안으로 한국에 직접 영향이 없는 경우 |

---

### 4.5 [5단계] 근거 검증 — Claude + Citations

기존 GPT-4o 교차검증을 대체한다.

#### 역할 재정의

| 구분 | 내용 |
|---|---|
| 기존 (잘못된 질문) | "이 뉴스가 진짜인가?" → 웹 접근 없이는 판정 불가, 전량 통과 |
| 변경 (올바른 질문) | "이 요약의 각 문장이 본문 어디에 근거하는가?" → 기계적 판정 가능 |

#### 구현 방식

기사 본문을 `search_result` 블록으로 전달하고 citations를 활성화한다. Claude가 각 주장을 뒷받침하는 본문 구절을 인용 블록으로 반환하므로, **근거 구절이 붙지 않은 문장 = 환각**으로 코드가 자동 판정할 수 있다.

```python
messages = [{
    "role": "user",
    "content": [
        {
            "type": "search_result",
            "source": article_url,
            "title": article_title,
            "content": [{"type": "text", "text": body_text}],
            "citations": {"enabled": True}
        },
        {
            "type": "text",
            "text": (
                "위 기사 본문을 근거로, 아래 요약문의 각 항목이 본문에 "
                "실제로 기재된 내용인지 검토하십시오. 각 항목마다 본문의 "
                "해당 구절을 인용하며 설명하십시오. 본문에서 근거를 찾을 수 "
                "없는 항목은 '근거 없음'이라고 명시하십시오.\n\n"
                f"[검토 대상 요약]\n{summary_json}"
            )
        }
    ]
}]
```

#### 판정 로직

응답의 citation 블록을 파싱하여 요약 10개 항목별로 근거 유무를 집계한다.

| 근거 없는 항목 수 | Review Status |
|---|---|
| 0개 | `Verified` |
| 1~2개 | `Needs-Review` (해당 항목을 `Research Notes`에 명기) |
| 3개 이상 | `Rejected` — 요약을 폐기하고 재생성 1회 시도 |

#### 제약사항 (구현 시 반드시 반영)

**Citations 기능은 Structured Outputs와 함께 사용할 수 없다.** 사용자 제공 문서나 `search_result` 블록에 citations를 활성화한 상태에서 `output_config.format` 파라미터를 함께 전달하면 API가 400 오류를 반환한다. 인용 블록을 텍스트 출력 사이에 끼워 넣는 방식이 엄격한 JSON 스키마 제약과 충돌하기 때문이다.

따라서 다음 중 하나를 택한다.

- **권장**: JSON 스키마를 강제하지 않고, 응답의 citation 블록을 코드로 직접 파싱하여 판정 결과를 조립
- 대안: 호출을 2회로 분리 (1회차 검증 → 2회차 JSON 정리). 비용·지연 증가

#### 웹 검색 비활성화

검증기에는 **웹 검색 도구를 붙이지 않는다.** URL 실존 확인은 2단계 코드의 HTTP 요청이 담당한다. 검증기에 검색을 붙이면 토큰이 증가할 뿐 아니라, 모델이 "유사한 기사를 찾았으므로 사실"이라고 판단할 여지가 생긴다. 검증기는 **본문과 요약만** 본다.

---

## 5. 모델 배치 및 비용

### 5.1 단계별 모델

| 단계 | 모델 | 모델 ID | 근거 |
|---|---|---|---|
| 1 발견 | 없음 (RSS) / Gemini 3.5 Flash | - | 기존 유지, groundingMetadata만 사용 |
| 2 검증 | 없음 (코드) | - | LLM 불필요 |
| 3 본문 | 없음 (trafilatura) | - | LLM 불필요 |
| 4 요약 | Gemini 3.5 Flash | - | 기존 유지, 비용·속도 유리 |
| 5-a 사전 분류 | Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | 기사/비기사 판별, 제목·본문 일치 확인 |
| 5-b 근거 검증 | **Claude Sonnet 5** | `claude-sonnet-5` | 주력 검증기 |
| 5-c 주간 감사 | Claude Opus 5 | `claude-opus-5` | 통과분 10% 샘플 재검증 |

### 5.2 Sonnet 5을 주력으로 선정한 근거

근거 검증은 긴 텍스트를 대조하는 작업이며, 창의성이나 심층 추론을 요구하지 않는다. 상위 모델을 전수 적용해도 정확도 개선 대비 비용 증가가 크다. Opus 5는 **검증기 자체가 정상 작동하는지 확인하는 주간 샘플 감사**에만 사용하여 비용을 1/10로 억제한다.

### 5.3 비용 추산

API 단가는 100만 토큰(MTok) 기준이며, Haiku 4.5가 입력 $1 / 출력 $5, Sonnet 5가 $2/$10, Opus 5가 $5/$25다. 단, Sonnet 5의 $2/$10은 2026년 8월 31일까지 적용된 도입 가격이며 이후 $3/$15로 조정되므로, **구현 착수 시점에 공식 가격 페이지에서 재확인할 것.**

기사 1건당 토큰 추산:

| 항목 | 토큰 |
|---|---|
| 기사 본문 | ~6,000 |
| 요약문 | ~1,500 |
| 시스템 프롬프트·루브릭 | ~500 |
| **입력 합계** | **~8,000** |
| 출력 (판정 결과) | ~600 |

| 모델 | 건당 비용 | 일 50건 | 월 환산 |
|---|---|---|---|
| Haiku 4.5 | 약 $0.011 | $0.55 | 약 $16 |
| Sonnet 5 ($3/$15 기준) | 약 $0.033 | $1.65 | 약 $50 |

### 5.4 비용 절감 옵션 (둘 다 적용 권장)

- **Batch API**: 비동기 작업의 입력·출력 토큰을 50% 할인하며, 야간 자동화나 실시간이 아닌 워크로드에 적합하다. AIKA는 예약 수집 구조이므로 그대로 적용 가능하다.
- **프롬프트 캐싱**: 반복되는 컨텍스트에 대해 90% 절감을 제공한다. 검증 루브릭과 시스템 프롬프트가 매 호출 동일하므로 적용 대상이다.

둘 다 적용 시 **월 $25 내외**로 예상된다.

---

## 6. 시트 스키마 변경

### 6.1 기존 17개 컬럼

`No.`, `Batch ID`, `수집일시`, `기사 게재일`, `제목`, `출처 미디어명`, `출처 URL`, `언어`, `Primary AI Category`, `News Topic`, `관련 기업명`, `한줄 요약`, `10줄 상세 요약`, `핵심 키워드`, `한국 시장 관련성`, `Review Status`, `Research Notes`

컬럼 구성 자체는 유지한다. 설계는 적절하다.

### 6.2 추가 컬럼 (3개)

| 컬럼명 | 값 | 용도 |
|---|---|---|
| `URL 검증상태` | `200` / `403` / `404` / `REDIRECT` | 2단계 V1 결과 |
| `게재일 출처` | `meta` / `json-ld` / `og` / `rss` | 2단계 V5에서 사용한 추출 경로 |
| `본문 확보` | `full` / `rss-desc` / `none` | 3단계 결과. `none`이면 요약 공란 |

### 6.3 Review Status 값 재정의

| 값 | 의미 |
|---|---|
| `Verified` | 5단계 통과. 전 항목 근거 확인 |
| `Needs-Review` | 근거 없는 항목 1~2개. 사람 확인 필요 |
| `Link-Only` | 본문 확보 실패. URL·제목만 유효, 요약 없음 |
| `Invalid` | 기존 데이터 재검증에서 탈락 (7장 참조) |

기존의 `Auto-Collected`, `New`는 폐기한다. 수집 방식이 아니라 **검증 결과**를 담는 컬럼이어야 한다.

### 6.4 Batch ID 형식 통일

```
NEWS-{YYYYMMDD}-{HHMM}-{채널}
예: NEWS-20260914-1030-RSS
```

### 6.5 `_rejected` 탭 신설

4.2.4 참조. 컬럼: `수집일시`, `Batch ID`, `탈락 사유`, `URL`, `제목(원문)`, `발견 채널`

---

## 7. 기존 데이터 처리

현재 115행에 대해 일괄 재검증 스크립트를 1회 실행한다.

1. 전 행의 `출처 URL`에 HTTP 요청 (2단계 V1~V4 적용)
2. 탈락 행의 `Review Status`를 `Invalid`로 변경 — **행을 삭제하지 않는다.** 문제 패턴 추적 자료로 보존한다.
3. 게재일이 컷오프(운영 기준일) 이전인 행은 `Review Status = Archived`로 별도 표시
4. 중복 URL 24건은 최초 1건만 남기고 나머지를 `Duplicate`로 표시

예상 결과: `Invalid` 약 25건, `Archived` 약 56건, 유효 잔존 약 34건.

---

## 8. Streamlit UI 변경사항

| 항목 | 변경 내용 |
|---|---|
| `목표 수집 기사 수` | **`검색 상한`으로 의미 변경.** 현재는 "이 숫자를 채워야 한다"로 해석되어 모델이 부족분을 생성하는 원인이 된다. 검증 통과분이 5건이면 5건만 저장하도록 변경 |
| 실행 결과 표시 | `수집 시도 40건 → 검증 통과 12건 (탈락: URL 오류 8, 기간 초과 15, 중복 5)` 형식으로 표시 |
| `기사 게재일 기준` | 설정값을 Google News RSS의 `when:Nd` 파라미터로 변환하여 **검색 단계에서** 적용 |
| 발견 채널 선택 | RSS / Google News / Gemini 그라운딩 개별 on-off 토글 추가 |
| 검증 통계 패널 | 최근 7일 탈락 사유별 집계 표시 (품질 모니터링용) |
| 모델 역할 스위처 | `검증: GPT-4o` → `검증: Claude Sonnet 5`로 변경 |

---

## 9. 구현 우선순위

| 순위 | 작업 | 기대 효과 |
|---|---|---|
| P0 | 2단계 검증 로직 구현 (V1~V7) | 가짜 URL 27% 즉시 차단 |
| P0 | Gemini `groundingMetadata` 읽도록 수정 | 결함 A 근본 해결 |
| P1 | RSS 수집 채널 구축 | 결함 A·B 동시 해결, 비용 절감 |
| P1 | Google News RSS `when:Nd` 적용 | 결함 B 해결 |
| P1 | 3단계 본문 확보 + 본문 없으면 요약 금지 | 10줄 요약 환각 차단 |
| P2 | 5단계 Claude Sonnet 5 + Citations 전환 | 요약 근거 검증 |
| P2 | `_rejected` 탭 + 통계 패널 | 품질 추적 체계 확보 |
| P3 | 카테고리 enum 고정, Batch ID 통일 | 데이터 일관성 |
| P3 | 기존 115행 재검증 | 데이터 정합성 회복 |

P0만 완료해도 현재 결함의 대부분이 차단된다.

---

## 10. 완료 판정 기준

재설계 완료 여부는 아래 테스트로 판정한다.

| No. | 테스트 | 기대 결과 |
|---|---|---|
| T1 | 1회 수집 실행 후 전 행의 URL에 HTTP 요청 | 200 응답률 100% |
| T2 | 전 행의 URL 도메인과 `출처 미디어명` 대조 | 불일치 0건 |
| T3 | 전 행의 `기사 게재일`이 설정 컷오프 이후인지 확인 | 위반 0건 |
| T4 | 시트 내 canonical URL 중복 검사 | 중복 0건 |
| T5 | `namu.wiki`, `google.com/search`, 도메인 루트 URL 검색 | 검출 0건 |
| T6 | `Primary AI Category` 고유값 개수 | 12개 이하 |
| T7 | `_rejected` 탭 기록 존재 여부 | 1건 이상 (탈락이 0건이면 검증 미작동 의심) |
| T8 | `본문 확보 = none`인 행의 요약 컬럼 | 공란 |
| T9 | 무작위 10건의 `10줄 상세 요약`을 원문과 수동 대조 | 본문 미기재 사실 0건 |

**T7이 핵심이다.** 탈락 건이 0건이면 검증 로직이 작동하지 않는 것이다. 현재 시스템의 상태가 정확히 그렇다.

---

## 부록 A. 참고 문서

- Claude API Citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude API Search Results 블록: https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude API Web Search Tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- Gemini Grounding Metadata: Google AI for Developers 문서의 Grounding with Google Search 항목

## 부록 B. 용어

| 용어 | 의미 |
|---|---|
| 그라운딩(Grounding) | LLM 응답을 외부 검색 결과에 근거시키는 기법 |
| canonical URL | 동일 문서의 대표 주소. `<link rel="canonical">`로 선언 |
| Citations | 응답의 각 주장에 근거 구절을 인용 블록으로 반환하는 Claude API 기능 |
| 환각(Hallucination) | 근거 없는 내용을 사실처럼 생성하는 현상 |
