# AIKA 기사 검색 및 URL 정합성 확보 수행계획서

| 항목 | 내용 |
|---|---|
| 문서 버전 | v1.0 |
| 작성일 | 2026-09-14 |
| 대상 시스템 | AIKA (aika.agichang.com / Streamlit) |
| 수행 주체 | 1인 (AI 코딩 도구 활용) |
| 목표 완료 | ASAP — 집중 작업 기준 2~3일 |
| 운영 방침 | **수집 중단 후 수리.** 병행 운영 없음 |
| 관련 문서 | AIKA 뉴스수집 파이프라인 재설계 사양서 v1.0 |

---

## 1. 목표와 범위

### 1.1 이번 수행의 목표

**시트에 기록되는 모든 기사의 출처 URL이 실제 해당 기사의 주소이고, 게재일이 설정한 기간 이내일 것.**

단 하나의 문장으로 요약되는 목표다. 이것이 달성되면 나머지 품질 문제는 후속 과제로 돌려도 된다.

### 1.2 범위에 포함 (In Scope)

| 구분 | 내용 |
|---|---|
| 기사 검색 | RSS 채널 신설, Google News RSS 날짜 필터, Gemini 그라운딩 메타데이터 전환 |
| URL 정합성 | HTTP 검증, 도메인 대조, 금지 패턴 차단, canonical 중복 제거 |
| 게재일 | HTML 메타데이터 추출, 컷오프 필터 |
| 데이터 | `_rejected` 탭 신설, 검증 컬럼 3개 추가, 기존 115행 재검증 |
| UI | 수집 결과 통계 표시, `목표 수집 수` → `검색 상한` 의미 변경 |

### 1.3 범위에서 제외 (Out of Scope — 2차 과제)

| 제외 항목 | 사유 |
|---|---|
| 본문 확보(trafilatura) 및 요약 환각 대책 | URL이 맞아야 본문을 가져올 수 있다. 선후관계상 다음 단계 |
| Claude Sonnet 5 근거 검증 전환 | 요약 품질 과제. URL 문제와 독립 |
| 카테고리 enum 고정, Batch ID 통일 | 정합성 개선이나 긴급도 낮음 |
| 한국 시장 관련성 판정 기준 | 요약 품질 과제 |

> 범위를 넓히면 ASAP이 불가능하다. **URL과 날짜만** 잡고 재가동한 뒤, 2차로 요약 품질에 착수하는 것이 맞다.

---

## 2. 착수 전 준비 (Phase 0)

**예상 소요: 1시간**

수리 시작 전에 반드시 완료한다. 이 단계를 건너뛰면 되돌릴 수 없다.

| No. | 작업 | 완료 조건 |
|---|---|---|
| 0-1 | 자동 예약 수집 **중단** | Streamlit 사이드바의 자동 수집 토글 OFF. cron/스케줄러가 별도면 그것도 중지 |
| 0-2 | 현재 시트 사본 생성 | `AI 뉴스 DB_백업_20260914` 형태로 사본 저장 |
| 0-3 | 소스 코드 백업 | 앱 폴더 전체 zip 압축 또는 git commit |
| 0-4 | 수집 모듈 파일 특정 | Gemini 호출부 / 응답 파싱부 / 시트 기록부가 각각 어느 파일 몇 번째 줄인지 확인 |
| 0-5 | 화이트리스트 도메인 목록 추출 | 현재 Streamlit `항시 우선 검색 도메인` 값을 텍스트로 확보 |

### 0-4 수행 방법

AI 코딩 도구에 다음과 같이 요청한다.

```
이 Streamlit 프로젝트에서 다음 세 곳의 위치를 찾아서 파일명과 줄 번호를 알려줘.
1. Gemini API를 호출하는 코드
2. Gemini 응답에서 기사 제목/URL/날짜를 추출하는 코드
3. Google Sheets에 행을 추가하는 코드
각각의 코드 블록도 함께 보여줘.
```

**이 단계의 결과가 이후 모든 작업의 출발점이다.** 3개 위치를 특정하지 못하면 다음 단계로 넘어가지 않는다.

---

## 3. 작업 단계

### Phase 1 — Gemini 응답 파싱 전환

**예상 소요: 2~3시간 / 우선순위: 최상**

가짜 URL의 발생 지점을 직접 차단한다. 단일 변경으로 가장 큰 효과를 낸다.

#### 작업 내용

| No. | 작업 |
|---|---|
| 1-1 | 현재 파싱 코드가 `groundingMetadata`를 읽는지 확인 |
| 1-2 | 응답 텍스트에서 URL을 추출하는 코드를 전부 제거 |
| 1-3 | `groundingChunks[].web.uri` / `.title`에서 추출하도록 교체 |
| 1-4 | vertexaisearch 리다이렉트 URL을 302 추적하여 최종 URL로 해석 |
| 1-5 | 해석 실패 시 해당 건 폐기 (추측 금지) |

#### AI 도구 작업 지시 예시

```
Gemini API 응답 파싱 코드를 수정해줘.

현재 문제: 응답 본문 텍스트(candidates[].content.parts[].text)에서
정규식 등으로 URL을 뽑아내고 있는데, 이 URL은 모델이 생성한 것이라
실제 존재하지 않는 주소다.

수정 방향:
1. 응답 텍스트에서 URL을 추출하는 코드는 전부 삭제
2. 대신 candidates[].groundingMetadata.groundingChunks[] 배열을 순회하며
   각 chunk의 web.uri 와 web.title 을 가져올 것
3. web.uri는 vertexaisearch.cloud.google.com/grounding-api-redirect/... 형태의
   리다이렉트 URL이므로, requests로 allow_redirects=True 요청을 보내
   response.url (최종 도착지)를 실제 기사 URL로 사용할 것
4. 리다이렉트 해석이 실패하거나 타임아웃되면 그 건은 버릴 것.
   절대 추측한 URL로 대체하지 말 것
5. groundingMetadata가 응답에 없으면 빈 리스트를 반환하고 로그를 남길 것

리다이렉트 URL은 만료 시간이 있으니 응답 수신 직후 즉시 해석해야 한다.
```

#### 완료 판정

- [ ] 수집 1회 실행 후, 반환된 URL을 브라우저에서 열었을 때 **해당 제목의 기사 페이지**가 뜬다
- [ ] `namu.wiki`, `google.com/search`, 도메인 루트만 있는 URL이 나오지 않는다
- [ ] `groundingMetadata`가 없을 때 조용히 실패하지 않고 로그가 남는다

> **Phase 1만 완료해도 가짜 URL의 상당수가 사라진다.** 여기서 한번 실행해 결과를 확인한 뒤 다음 단계로 넘어갈 것.

---

### Phase 2 — URL 검증 모듈 신설

**예상 소요: 3~4시간 / 우선순위: 최상**

Phase 1을 통과한 URL도 전부 이 관문을 거친다. 발견 채널이 무엇이든 검증은 동일하게 적용된다.

#### 작업 내용

독립 모듈 `validator.py`를 신설한다. 입력은 URL 후보, 출력은 통과/탈락 판정이다.

| 검사 | 내용 | 탈락 사유 코드 |
|---|---|---|
| V1 | HTTP 최종 응답 200 | `HTTP_{코드}` |
| V2 | 최종 도메인이 화이트리스트에 포함 | `DOMAIN_NOT_ALLOWED` |
| V3 | 도메인이 출처 미디어명과 일치 | `SOURCE_MISMATCH` |
| V4 | 금지 패턴 미해당 | `INVALID_URL_PATTERN` |
| V5 | 페이지에서 게재일 추출 성공 | `NO_PUBLISH_DATE` |
| V6 | 게재일이 설정 컷오프 이후 | `TOO_OLD` |
| V7 | canonical URL이 기존 시트에 없음 | `DUPLICATE` |

#### AI 도구 작업 지시 예시

```
validator.py 라는 새 모듈을 만들어줘.

함수 시그니처:
def validate_article(url: str, source_media: str, cutoff_date: date,
                     existing_urls: set) -> dict

반환값:
{"passed": bool, "reason": str, "final_url": str,
 "published_at": str|None, "date_source": str|None, "http_status": int}

검증 순서 (실패 시 즉시 반환, 이후 검사 생략):

V1. requests.get(url, allow_redirects=True, timeout=10) 으로 최종 상태 확인.
    200이 아니면 reason="HTTP_{상태코드}"

V2. 최종 URL의 도메인이 허용 목록에 있는지 확인.
    없으면 reason="DOMAIN_NOT_ALLOWED"

V3. 도메인과 source_media 매핑 대조.
    예: source_media가 "ZDNet Korea"인데 도메인이 zdnet.co.kr이 아니면
    reason="SOURCE_MISMATCH"
    매핑 테이블은 딕셔너리로 분리해서 관리

V4. 아래 금지 패턴에 하나라도 걸리면 reason="INVALID_URL_PATTERN"
    - namu\.wiki
    - google\.com/search
    - google\.com/url\?
    - youtube\.com
    - ^https?://[^/]+/?$      (경로 없이 도메인만 있는 URL)
    - /search\?
    - \.(pdf|zip|jpg|png)$

V5. HTML에서 게재일을 아래 순서로 탐색:
    1) <meta property="article:published_time">
    2) JSON-LD 스크립트의 datePublished
    3) <meta property="og:published_time">
    4) <meta name="date"> 또는 <time datetime="">
    전부 실패하면 reason="NO_PUBLISH_DATE"
    성공하면 date_source에 사용한 경로를 기록 (meta / json-ld / og / time)
    ※ 게재일을 LLM에게 묻는 코드는 절대 넣지 말 것

V6. 추출한 게재일이 cutoff_date 이전이면 reason="TOO_OLD"

V7. canonical URL 정규화 후 existing_urls에 있으면 reason="DUPLICATE"
    정규화 규칙:
    - <link rel="canonical"> 값이 있으면 그것을 사용
    - utm_*, fbclid, gclid 파라미터 제거
    - 말미 슬래시 제거, 스킴을 https로 통일

요청 시 브라우저 User-Agent 헤더를 설정하고,
동일 도메인 연속 요청 사이에 1.5초 지연을 넣을 것.
```

#### 완료 판정

- [ ] 기존 시트의 문제 URL 10개를 넣었을 때 전부 탈락한다
  - `https://namu.wiki/w/삼성` → `INVALID_URL_PATTERN`
  - `https://www.anthropic.com/` → `INVALID_URL_PATTERN`
  - `https://corporate.jcpenney.com/` → `DOMAIN_NOT_ALLOWED`
  - `https://www.google.com/search?q=...` → `INVALID_URL_PATTERN`
- [ ] 정상 기사 URL 5개를 넣었을 때 전부 통과하고 게재일이 정확히 추출된다
- [ ] 파이프라인에서 검증 통과 건만 시트에 기록된다

---

### Phase 3 — 검색 단계 날짜 필터 및 RSS 채널

**예상 소요: 3~4시간 / 우선순위: 상**

Phase 2가 오래된 기사를 걸러내긴 하지만, 그건 사후 차단이다. 애초에 오래된 기사를 가져오지 않는 것이 효율적이다.

#### 작업 내용

| No. | 작업 |
|---|---|
| 3-1 | Google News RSS 채널 추가, `when:Nd` 파라미터 적용 |
| 3-2 | Streamlit `기사 게재일 기준` 값을 `when:Nd`로 변환하는 로직 |
| 3-3 | 주요 매체 RSS 직접 수집 채널 추가 |
| 3-4 | RSS 엔드포인트 설정 파일(`sources.yaml`) 분리 |
| 3-5 | 발견 채널별 on-off 토글 UI 추가 |

#### RSS 엔드포인트 확인 (3-3 선행 작업)

아래 목록은 **후보**다. 매체 개편으로 변경되었을 수 있으므로 착수 전 각 주소에 실제 요청을 보내 200 응답과 파싱 가능 여부를 확인한다. 실패한 매체는 Google News RSS로 대체한다.

| 매체 | RSS 엔드포인트 후보 | 확인 |
|---|---|---|
| ZDNet Korea | `https://zdnet.co.kr/news/news_xml.asp` | ☐ |
| 전자신문 | `https://rss.etnews.com/Section901.xml` | ☐ |
| TechCrunch | `https://techcrunch.com/feed/` | ☐ |
| VentureBeat | `https://venturebeat.com/feed/` | ☐ |
| The Verge | `https://www.theverge.com/rss/index.xml` | ☐ |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` | ☐ |
| Wired | `https://www.wired.com/feed/rss` | ☐ |
| AI타임스 | `https://www.aitimes.com/rss/allArticle.xml` | ☐ |
| 디지털데일리 | `https://www.ddaily.co.kr/rss/allArticle.xml` | ☐ |

#### AI 도구 작업 지시 예시

```
뉴스 발견 단계에 두 개 채널을 추가해줘.

[채널 A] Google News RSS
URL 형식:
https://news.google.com/rss/search?q={쿼리}+when:{N}d&hl=ko&gl=KR&ceid=KR:ko

- {N}은 Streamlit의 "기사 게재일 기준" 설정값과 오늘 날짜의 차이(일수)로 계산
- 반환되는 link는 news.google.com 리다이렉트이므로
  302를 추적해 최종 URL로 해석한 뒤 저장
- 각 item에서 title, link, pubDate, source를 그대로 가져올 것.
  이 값들을 LLM으로 가공하지 말 것

[채널 B] 매체 RSS 직접 수집
- feedparser 라이브러리 사용
- 엔드포인트 목록은 sources.yaml 설정 파일로 분리
  (코드에 하드코딩하지 말 것)
- 각 entry에서 title, link, published, summary를 추출
- published가 컷오프 이전이면 이 단계에서 바로 제외

두 채널 모두 결과를 아래 공통 형식으로 반환:
{"url": ..., "title_raw": ..., "published_at_raw": ...,
 "source_media_raw": ..., "discovery_channel": "google_news"|"rss"|"gemini"}

기존 Gemini 채널의 출력도 이 형식에 맞춰 통일하고,
세 채널의 결과를 합친 뒤 validator.validate_article()로 넘길 것.
```

#### 완료 판정

- [ ] RSS 채널 단독 실행 시 컷오프 이전 기사가 1건도 나오지 않는다
- [ ] Google News RSS의 리다이렉트가 최종 매체 URL로 해석된다
- [ ] 3개 채널의 출력 형식이 동일하고 검증 모듈로 통합 전달된다

---

### Phase 4 — 시트 스키마 및 결과 표시

**예상 소요: 2시간 / 우선순위: 중**

검증이 실제로 작동하는지 눈으로 확인할 수 있게 만든다.

#### 작업 내용

| No. | 작업 |
|---|---|
| 4-1 | 컬럼 3개 추가: `URL 검증상태`, `게재일 출처`, `본문 확보` |
| 4-2 | `_rejected` 탭 신설 및 탈락 건 기록 |
| 4-3 | Streamlit 실행 결과에 수집 통계 표시 |
| 4-4 | `목표 수집 기사 수` → `검색 상한`으로 의미 변경 |

#### 4-4가 중요한 이유

현재 `목표 수집 기사 수: 10`은 모델에게 "10건을 채워야 한다"는 압박으로 작동한다. 실제 검색 결과가 3건뿐이어도 나머지 7건을 만들어내는 원인이 된다.

**검증 통과분이 3건이면 3건만 저장하도록** 변경한다. 부족분을 채우려 재시도하지 않는다.

#### 결과 표시 형식

```
수집 시도 40건 → 검증 통과 12건
탈락 내역: URL 오류 8 / 기간 초과 15 / 중복 5
```

#### 완료 판정

- [ ] 수집 1회 실행 후 `_rejected` 탭에 탈락 건이 기록된다
- [ ] 시도 건수와 통과 건수가 화면에 표시된다
- [ ] 통과 건수가 설정값보다 적어도 추가 수집을 시도하지 않는다

---

### Phase 5 — 기존 115행 재검증

**예상 소요: 1~2시간 / 우선순위: 중**

신규 수집이 정상화된 뒤 실행한다.

#### 작업 내용

일회성 스크립트로 기존 115행 전체를 `validate_article()`에 통과시킨다.

| 판정 | 처리 |
|---|---|
| V1~V4 탈락 | `Review Status = Invalid` |
| V6 탈락 (기간 초과) | `Review Status = Archived` |
| V7 탈락 (중복) | 최초 1건만 남기고 `Review Status = Duplicate` |
| 통과 | `Review Status = Verified` |

**행을 삭제하지 않는다.** 문제 패턴 추적 자료로 보존한다.

#### 예상 결과

| 판정 | 예상 건수 |
|---|---|
| Invalid | 약 25건 |
| Archived | 약 56건 |
| Duplicate | 약 24건 |
| 유효 잔존 | 약 34건 |

실제 결과가 이 범위에서 크게 벗어나면 검증 로직을 재점검한다.

---

## 4. 일정 요약

집중 작업 기준이며, AI 도구 활용을 전제로 한다.

| Phase | 작업 | 소요 | 누적 |
|---|---|---|---|
| 0 | 준비·백업·코드 위치 특정 | 1h | 1h |
| 1 | Gemini 파싱 전환 | 2~3h | 4h |
| 2 | URL 검증 모듈 | 3~4h | 8h |
| — | **1차 검수 및 시험 수집** | 1h | 9h |
| 3 | 날짜 필터 + RSS 채널 | 3~4h | 13h |
| 4 | 스키마·결과 표시 | 2h | 15h |
| 5 | 기존 데이터 재검증 | 1~2h | 17h |
| — | **최종 검수 및 재가동** | 1h | 18h |

**총 18시간 ≒ 집중 작업 2~3일**

### 단계 게이트

각 Phase 완료 판정을 통과하지 못하면 다음 단계로 넘어가지 않는다. 특히 다음 두 지점은 반드시 지킨다.

- **Phase 1 완료 후 반드시 1회 시험 수집**을 돌려 URL이 실제로 열리는지 확인한다. 여기서 문제가 남아 있으면 Phase 2 이후 작업이 잘못된 전제 위에 쌓인다.
- **Phase 2 완료 후 1차 검수**를 거쳐 자동 수집을 임시 재개해도 된다. Phase 3~5는 그 뒤에 이어가도 무방하다.

---

## 5. 검수 기준

재가동 전 아래를 전부 확인한다.

| No. | 검사 | 방법 | 기준 |
|---|---|---|---|
| T1 | URL 실존 | 수집 결과 전 행에 HTTP 요청 | 200 응답률 100% |
| T2 | URL-매체 일치 | 도메인과 `출처 미디어명` 대조 | 불일치 0건 |
| T3 | 기사 일치 | 무작위 10건을 브라우저에서 열기 | 제목과 페이지 내용 일치 10/10 |
| T4 | 게재일 | 컷오프 이후인지 확인 | 위반 0건 |
| T5 | 중복 | canonical URL 중복 검사 | 중복 0건 |
| T6 | 금지 패턴 | `namu.wiki`, `google.com/search`, 도메인 루트 검색 | 검출 0건 |
| T7 | **탈락 기록** | `_rejected` 탭 확인 | **1건 이상** |

### T7이 가장 중요하다

탈락 건이 0건이면 검증이 작동하지 않는 것이다. 현재 시스템이 정확히 그 상태다 — 시트에 `Invalid` 판정이 단 한 건도 없다.

정상적인 파이프라인은 **반드시 무언가를 버린다.** 시도 40건 중 통과 12건이면 정상이고, 시도 40건 중 통과 40건이면 검증이 무력화된 것이다.

---

## 6. 리스크와 대응

| 리스크 | 발생 가능성 | 영향 | 대응 |
|---|---|---|---|
| `groundingMetadata`가 응답에 없음 | 중 | Phase 1 무효 | Gemini 호출 시 그라운딩 도구가 실제 활성화되었는지 확인. 응답 원본을 JSON으로 덤프해 구조 직접 확인 |
| RSS 엔드포인트 변경·중단 | 중 | 채널 B 일부 실패 | 해당 매체는 Google News RSS로 대체. `sources.yaml`에서 비활성화 |
| 국내 매체 봇 차단 (403) | 중 | 게재일 추출 실패 | User-Agent 설정, 요청 간격 2초. 그래도 실패하면 RSS `pubDate` 사용 |
| 검증 통과 건수 급감 | **높음** | 수집량 감소 | **정상 현상이다.** 기존 115건 중 유효분은 약 34건이었다. 통과율 30~50%를 정상 범위로 간주하고, 수집량은 검색 상한을 올려 확보 |
| 수집 중단 기간 중 뉴스 누락 | 낮음 | 2~3일 공백 | RSS는 과거 기사도 제공하므로 재가동 후 컷오프를 앞당겨 1회 소급 수집 |

### 특히 유의할 점

**Phase 2 적용 직후 수집량이 급감하는 것은 실패가 아니라 성공 신호다.** 지금까지는 검증 없이 전부 통과시켰기 때문에 숫자가 많았을 뿐이다. 숫자가 줄었다고 검증을 느슨하게 되돌리면 원점으로 돌아간다.

---

## 7. 완료 선언 조건

아래를 모두 만족하면 이번 수행을 종료하고 2차 과제(요약 품질)로 이행한다.

- [ ] Phase 0~5 완료 판정 전부 통과
- [ ] 검수 T1~T7 전부 통과
- [ ] 시험 수집 3회 연속으로 T1·T3 위반 0건
- [ ] `_rejected` 탭에 탈락 사유별 기록 축적 확인
- [ ] 자동 예약 수집 재가동 및 익일 결과 정상 확인

---

## 부록. 2차 과제 (본 수행 완료 후)

| 순위 | 과제 | 사양서 참조 |
|---|---|---|
| 1 | 본문 확보(trafilatura) 및 본문 없으면 요약 생성 금지 | 4.3절 |
| 2 | Claude Sonnet 5 + Citations 근거 검증 전환 | 4.5절 |
| 3 | 카테고리 enum 12종 고정, News Topic 6종 고정 | 4.4절 |
| 4 | 한국 시장 관련성 판정 기준 명문화 | 4.4절 |
| 5 | Batch ID 형식 통일 | 6.4절 |
