# IT 보안·리스크 요약 + SAP 운영 Q&A 통합 에이전트 — 개발 명세서

> **용도**: 코드 에이전트(Code Agent)에 전달하는 구현 명세서  
> **버전**: v2.0 (Streamlit + GPT-4o-mini 전환)  
> **작성일**: 2026-05-14  
> **변경 이력**: v1.0 → v2.0 — UI 프레임워크를 Next.js에서 Streamlit으로 변경, LLM을 Claude에서 GPT-4o-mini로 변경, API Key를 화면 입력 방식으로 변경, 외부 인프라(PostgreSQL·Redis·Docker) 제거

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택](#2-기술-스택)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [v1.0 대비 변경 사항 요약](#4-v10-대비-변경-사항-요약)
5. [파이프라인 A — 실시간 리스크 요약](#5-파이프라인-a--실시간-리스크-요약)
6. [파이프라인 B — SAP 운영 Q&A](#6-파이프라인-b--sap-운영-qa)
7. [공통 모듈](#7-공통-모듈)
8. [기능 목록 및 세부 요건](#8-기능-목록-및-세부-요건)
9. [Streamlit 화면 구성](#9-streamlit-화면-구성)
10. [데이터 모델 (인메모리·파일 기반)](#10-데이터-모델-인메모리파일-기반)
11. [디렉터리 구조](#11-디렉터리-구조)
12. [구현 우선순위 및 단계](#12-구현-우선순위-및-단계)
13. [테스트 요건](#13-테스트-요건)
14. [비기능 요건](#14-비기능-요건)

---

## 1. 프로젝트 개요

### 1.1 서비스 목적

외부 보안·취약점·장애 공지·IT 뉴스를 자동 수집해 IT 운영자 관점의 리스크 브리핑을 생성하고, SAP 운영 중 발생하는 오류 메시지 및 T-code 관련 질문에 SAP 공식 문서 기반으로 정확한 답변을 제공하는 통합 LLM 에이전트 서비스입니다.

**Streamlit 전환 목적**: 빠른 프로토타입 및 데모 제공. 별도 백엔드 서버·DB 없이 단일 Python 앱으로 즉시 실행 가능.

### 1.2 핵심 방법론

| 파이프라인 | 방법론 | 비고 |
|---|---|---|
| 파이프라인 A (리스크 요약) | LLM 에이전트 + 룰 기반 필터 | GPT-4o-mini 호출 |
| 파이프라인 B (SAP Q&A) | RAG + LLM (하이브리드 검색) | ChromaDB(인메모리) + GPT-4o-mini |
| 의도 분류 | LLM 기반 라우터 | GPT-4o-mini 호출 |

### 1.3 주요 플로우 요약

```
[Streamlit 사이드바] → API Key 입력 → 세션 상태에 저장

[탭 1: 리스크 브리핑]
  버튼 클릭 → 외부 소스 수집 → 룰 필터 → GPT-4o-mini 요약 → 화면 출력

[탭 2: SAP Q&A]
  질문 입력 → 의도 분류 → 하이브리드 검색(ChromaDB) → RAG 답변 → 채팅 화면 출력
```

---

## 2. 기술 스택

### 2.1 전체 스택 (단일 Python 앱)

```
언어:             Python 3.11+
UI 프레임워크:    Streamlit 1.35+
LLM:              OpenAI GPT-4o-mini  (openai>=1.30)
임베딩:           text-embedding-3-small  (openai)
벡터 DB:          ChromaDB 0.5+  (인메모리, 영속화 시 로컬 파일)
키워드 검색:      rank_bm25
크롤러:           httpx, feedparser, beautifulsoup4
상태 관리:        st.session_state  (Streamlit 내장)
데이터 저장:      JSON 파일 (로컬, 선택적)  — DB 없음
스케줄:           Streamlit 버튼 트리거 / apscheduler (백그라운드 스레드)
```

### 2.2 주요 패키지 (`requirements.txt`)

```
streamlit>=1.35.0
openai>=1.30.0
chromadb>=0.5.0
rank_bm25>=0.2.2
feedparser>=6.0.11
httpx>=0.27.0
beautifulsoup4>=4.12.0
lxml>=5.2.0
python-dotenv>=1.0.0
pydantic>=2.7.0
apscheduler>=3.10.4
pandas>=2.2.0
```

### 2.3 제거된 항목 (v1.0 → v2.0)

| v1.0 항목 | v2.0 대체 | 이유 |
|---|---|---|
| FastAPI | 제거 (Streamlit 단독) | 별도 API 서버 불필요 |
| Next.js + shadcn/ui | Streamlit UI | 프론트엔드 분리 불필요 |
| PostgreSQL + SQLAlchemy | JSON 파일 / st.session_state | 외부 DB 의존성 제거 |
| Redis | st.session_state + 인메모리 dict | 캐시 단순화 |
| Docker / Docker Compose | 제거 (`pip install` 후 직접 실행) | 환경 단순화 |
| Claude (Anthropic) | OpenAI GPT-4o-mini | 모델 변경 |
| SAML/OIDC SSO | 제거 | 단순 API Key 인증으로 대체 |
| RBAC (admin/operator/viewer) | 제거 | 단일 사용자 시나리오 |
| SIEM 연동 | 제거 | 프로토타입 범위 외 |

---

## 3. 시스템 아키텍처

### 3.1 컴포넌트 구조 (단일 앱)

```
streamlit_app.py  (진입점)
│
├── sidebar_config()          ← API Key 입력, 회사 컨텍스트 설정
│
├── [탭 1] risk_briefing_tab()
│   ├── FeedCollector         ← RSS/API 수집
│   ├── DuplicateFilter       ← 세션 내 중복 제거 (set)
│   ├── RuleFilter            ← CVSS·키워드 필터
│   └── LLMSummarizer         ← GPT-4o-mini 요약
│
├── [탭 2] sap_qa_tab()
│   ├── InputPreprocessor     ← 오류코드·T-code 추출
│   ├── IntentClassifier      ← GPT-4o-mini 분류
│   ├── HybridSearcher        ← BM25 + ChromaDB 벡터
│   ├── RAGGenerator          ← GPT-4o-mini RAG 답변
│   └── SessionManager        ← st.session_state 대화 이력
│
├── [탭 3] dashboard_tab()
│   └── 수집 현황, 질의 이력, 피드백 통계 (세션 내)
│
└── [탭 4] settings_tab()
    └── 컨텍스트 편집, SAP 문서 인덱싱 트리거
```

### 3.2 API Key 처리 방식

```python
# sidebar_config() 내부
with st.sidebar:
    st.header("설정")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",          # 마스킹 표시
        placeholder="sk-...",
        help="키는 세션 내에서만 유지되며 저장되지 않습니다."
    )
    if api_key:
        st.session_state["openai_api_key"] = api_key
        st.success("API Key 설정됨", icon="✅")
    else:
        st.warning("API Key를 입력하세요.")
        st.stop()   # Key 없으면 이하 실행 중단

# LLM 호출 시
client = openai.OpenAI(api_key=st.session_state["openai_api_key"])
```

**보안 주의사항 (코드 주석으로 명시)**:
- API Key는 `st.session_state`에만 존재하며 파일·로그에 절대 기록하지 않음
- `type="password"` 필수 (화면 마스킹)
- 세션 종료 시 자동 소멸

---

## 4. v1.0 대비 변경 사항 요약

### 4.1 기능별 변경 매핑

| 기능 | v1.0 | v2.0 (Streamlit) | 변경 여부 |
|---|---|---|---|
| F-01 외부 소스 수집 | 백그라운드 스케줄러 자동 | 버튼 클릭 수동 + 선택적 백그라운드 스레드 | **변경** |
| F-02 룰 기반 필터 | DB 동적 로드 | 사이드바 UI 직접 설정 → session_state | **변경** |
| F-03 LLM 리스크 요약 | Claude claude-sonnet-4-20250514 | GPT-4o-mini | **변경** |
| F-04 일일 브리핑 스케줄러 | APScheduler + Slack/메일 발송 | 버튼 수동 실행, 결과 화면 표시 (알림 발송 선택적) | **변경** |
| F-05 SAP 문서 인덱싱 | pgvector + 자동 증분 | ChromaDB 인메모리 + 탭4 수동 트리거 | **변경** |
| F-06 하이브리드 검색 | Elasticsearch + pgvector | rank_bm25 + ChromaDB | **변경** |
| F-07 SAP Q&A | Claude RAG | GPT-4o-mini RAG | **변경** |
| F-08 멀티턴 세션 | PostgreSQL 영구 저장 | st.session_state (세션 내 유지) | **변경** |
| F-09 알림 채널 연동 | Slack/Teams/이메일 자동 발송 | 선택적 (Slack Webhook URL 입력 시 발송) | **축소** |
| F-10 회사 IT 컨텍스트 관리 | DB 버전 이력 관리 | 사이드바 입력 + JSON 파일 저장 (선택) | **변경** |
| F-11 의도 분류 및 라우팅 | 별도 서비스 | GPT-4o-mini 인라인 호출 | **유지** |
| F-12 응답 품질 피드백 | DB 저장 + 검토 큐 | st.session_state 내 누적, 탭3에서 확인 | **변경** |
| F-13 통합 대시보드 | Next.js 별도 페이지 | Streamlit 탭3 (pandas + st.dataframe) | **변경** |
| F-14 접근 제어 및 감사 로그 | RBAC + SSO + SIEM | **제거** (API Key 단일 인증으로 대체) | **제거** |

### 4.2 LLM 모델 변경

| 항목 | v1.0 | v2.0 |
|---|---|---|
| 모델명 | `claude-sonnet-4-20250514` | `gpt-4o-mini` |
| API 클라이언트 | `anthropic` | `openai` |
| 스트리밍 | `stream=True` (Anthropic SSE) | `stream=True` (OpenAI SSE) |
| 임베딩 | `text-embedding-3-small` (동일) | `text-embedding-3-small` |
| 최대 토큰 | 4096 | 4096 (동일) |
| 컨텍스트 윈도우 | 200K | 128K |

```python
# v2.0 LLM 호출 표준 패턴
from openai import OpenAI

def call_llm(prompt: str, system: str, stream: bool = False):
    client = OpenAI(api_key=st.session_state["openai_api_key"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4096,
        stream=stream
    )
    if stream:
        return response   # st.write_stream()에 전달
    return response.choices[0].message.content
```

---

## 5. 파이프라인 A — 실시간 리스크 요약

### 5.1 플로우

```
[탭1 버튼 클릭]
  → FeedCollector.collect_all()       # RSS/API 비동기 수집
  → DuplicateFilter.filter()          # session_state set 기반 중복 제거
  → RuleFilter.apply()                # CVSS 임계값·키워드 필터
  → 항목 0개? → "이상 없음" 메시지 표시
  → LLMSummarizer.summarize()         # GPT-4o-mini 스트리밍 요약
  → Critical 존재? → 빨간 배너 강조 표시
  → st.markdown() 결과 출력
  → session_state["briefing_history"] 에 저장
```

### 5.2 구현 명세

#### `FeedCollector` (`pipelines/risk/collector.py`)

```python
import feedparser, httpx
from pydantic import BaseModel

class RawFeedItem(BaseModel):
    source: str
    title: str
    url: str
    summary: str
    published: str
    cvss_score: float | None = None

SOURCES = [
    {"name": "NVD CVE",     "url": "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss-analyzed.xml", "type": "rss"},
    {"name": "CISA KEV",    "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", "type": "json"},
    {"name": "KrCERT",      "url": "https://www.krcert.or.kr/rss/vulnerability.do", "type": "rss"},
    {"name": "AWS Status",  "url": "https://status.aws.amazon.com/rss/all.rss", "type": "rss"},
    {"name": "HackerNews",  "url": "https://feeds.feedburner.com/TheHackersNews", "type": "rss"},
]

class FeedCollector:
    def collect_all(self) -> list[RawFeedItem]:
        items = []
        for src in SOURCES:
            try:
                items.extend(self._collect_one(src))
            except Exception as e:
                st.warning(f"[{src['name']}] 수집 실패: {e}")
        return items
```

#### `DuplicateFilter` (`pipelines/risk/dedup.py`)

```python
# session_state["seen_hashes"] = set() 초기화 필요
import hashlib

class DuplicateFilter:
    def filter(self, items: list[RawFeedItem]) -> list[RawFeedItem]:
        seen = st.session_state.setdefault("seen_hashes", set())
        result = []
        for item in items:
            h = hashlib.sha256((item.url + item.title).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                result.append(item)
        return result
```

#### `RuleFilter` (`pipelines/risk/rule_filter.py`)

```python
# 필터 기준은 st.session_state["filter_config"] 에서 로드
# 사이드바에서 설정한 값 사용

class RuleFilter:
    def apply(self, items: list[RawFeedItem]) -> list[RawFeedItem]:
        cfg = st.session_state.get("filter_config", {})
        min_cvss = cfg.get("min_cvss", 7.0)
        whitelist = cfg.get("whitelist_keywords", [])
        blacklist = cfg.get("blacklist_keywords", [])
        # 필터 로직 ...
        return filtered
```

#### `LLMSummarizer` (`pipelines/risk/summarizer.py`)

```python
RISK_SYSTEM_PROMPT = "당신은 IT 운영자를 위한 보안 리스크 분석가입니다."

RISK_USER_PROMPT = """
아래 수집된 보안·장애 공지를 분석해 오늘의 리스크를 요약하세요.

[회사 IT 환경]
{company_context}

[수집 항목 ({count}건)]
{feed_items}

출력 형식:
## 오늘의 핵심 리스크 (우선순위 순)
### 1. [리스크명] — 심각도: Critical/High/Medium
- **영향 범위**: ...
- **조치 권고**: ...
- **참고**: [링크]

## Critical 항목 여부
- Critical: 있음/없음
"""

class LLMSummarizer:
    def summarize(self, items: list[RawFeedItem], company_ctx: str) -> str:
        prompt = RISK_USER_PROMPT.format(
            company_context=company_ctx,
            count=len(items),
            feed_items="\n".join([f"- [{i.source}] {i.title} (CVSS: {i.cvss_score})" for i in items])
        )
        # st.write_stream() 으로 스트리밍 출력
        stream = call_llm(prompt, RISK_SYSTEM_PROMPT, stream=True)
        return st.write_stream(stream)
```

---

## 6. 파이프라인 B — SAP 운영 Q&A

### 6.1 플로우

```
[탭2 채팅 입력]
  → InputPreprocessor.preprocess()    # 오류코드·T-code 정규식 추출
  → IntentClassifier.classify()       # GPT-4o-mini 분류
      ├─ sap_qa      → HybridSearcher → RAGGenerator
      ├─ risk_query  → "리스크 브리핑 탭을 이용하세요" 안내
      ├─ cross       → 두 파이프라인 결과 병합
      └─ other       → "SAP 또는 보안 관련 질문만 지원합니다" 안내
  → 신뢰도 낮음? → "의도를 다시 확인해 주세요" 재질문
  → HybridSearcher.search()           # BM25 + ChromaDB 벡터 검색
  → 결과 없음? → "관련 문서를 찾지 못했습니다" 안내
  → RAGGenerator.generate()           # GPT-4o-mini 스트리밍 답변
  → 신뢰도 낮음? → 면책 문구 추가
  → st.chat_message() 출력
  → session_state["chat_history"] 저장
```

### 6.2 ChromaDB 인덱싱

```python
# pipelines/sap/indexer.py
import chromadb
from openai import OpenAI

def get_chroma_collection():
    """인메모리 ChromaDB 컬렉션 반환 (세션 내 유지)"""
    if "chroma_client" not in st.session_state:
        st.session_state["chroma_client"] = chromadb.Client()  # 인메모리
    client = st.session_state["chroma_client"]
    return client.get_or_create_collection("sap_docs")

def index_documents(urls: list[str]):
    """SAP 문서 URL 목록을 크롤링 후 임베딩·저장"""
    collection = get_chroma_collection()
    oai = OpenAI(api_key=st.session_state["openai_api_key"])
    
    for url in urls:
        chunks = crawl_and_chunk(url, chunk_size=512, overlap=50)
        embeddings = oai.embeddings.create(
            input=[c.text for c in chunks],
            model="text-embedding-3-small"
        ).data
        collection.add(
            ids=[c.id for c in chunks],
            embeddings=[e.embedding for e in embeddings],
            documents=[c.text for c in chunks],
            metadatas=[{"url": url, "sap_version": c.sap_version} for c in chunks]
        )
```

### 6.3 하이브리드 검색

```python
# pipelines/sap/searcher.py
from rank_bm25 import BM25Okapi

class HybridSearcher:
    def search(self, query: ProcessedQuery, top_k: int = 5) -> list[DocumentChunk]:
        collection = get_chroma_collection()
        
        # 벡터 검색
        oai = OpenAI(api_key=st.session_state["openai_api_key"])
        q_embed = oai.embeddings.create(
            input=query.normalized, model="text-embedding-3-small"
        ).data[0].embedding
        vector_results = collection.query(query_embeddings=[q_embed], n_results=top_k)
        
        # BM25 키워드 검색
        all_docs = collection.get()
        bm25 = BM25Okapi([d.split() for d in all_docs["documents"]])
        bm25_scores = bm25.get_scores(query.normalized.split())
        
        # Reciprocal Rank Fusion 병합
        return self._rrf_merge(vector_results, bm25_scores, all_docs, top_k)
```

### 6.4 RAG 답변 생성

```python
SAP_SYSTEM_PROMPT = "당신은 SAP 운영 전문가입니다. 반드시 제공된 문서를 근거로만 답변하세요."

SAP_USER_PROMPT = """
[참고 문서]
{retrieved_chunks}

[회사 SAP 환경]
{company_context}

[질문]
{user_question}

답변 형식:
## 원인 분석
## 단계별 해결 절차
1. ...
## 관련 T-code / 대체 방법
## 참고 문서
- [제목](URL)

문서에 없는 내용은 추측하지 말고 명시하세요.
"""
```

### 6.5 멀티턴 세션 (`st.session_state`)

```python
# session_state 초기화 (앱 시작 시)
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []   # [{"role": "user"|"assistant", "content": "..."}]

# 채팅 UI 렌더링
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 새 입력 처리
if prompt := st.chat_input("SAP 오류 또는 T-code를 입력하세요"):
    st.session_state["chat_history"].append({"role": "user", "content": prompt})
    # ... 처리 후 ...
    st.session_state["chat_history"].append({"role": "assistant", "content": answer})
```

---

## 7. 공통 모듈

### 7.1 회사 IT 컨텍스트 (`core/context_manager.py`)

```python
# 사이드바에서 입력받아 session_state 저장
# 선택적으로 context.json 파일로 영속화

DEFAULT_CONTEXT = {
    "os_stack": [],
    "middleware": [],
    "cloud": [],
    "sap_version": "",
    "sap_modules": [],
    "custom_keywords": []
}

def render_context_sidebar():
    with st.sidebar.expander("회사 IT 환경 설정"):
        ctx = st.session_state.setdefault("company_context", DEFAULT_CONTEXT.copy())
        ctx["sap_version"] = st.selectbox("SAP 버전", ["S/4HANA 2023", "S/4HANA 2022", "ECC 6.0", "기타"])
        ctx["cloud"] = st.multiselect("클라우드", ["AWS", "Azure", "GCP", "온프레미스"])
        ctx["os_stack"] = st.multiselect("OS", ["RHEL", "Ubuntu", "Windows Server", "SUSE"])
        ctx["custom_keywords"] = st.text_input("추가 키워드 (쉼표 구분)").split(",")
```

### 7.2 피드백 (`core/feedback.py`)

```python
# 각 답변 하단에 버튼 렌더링
def render_feedback(item_id: str):
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("👍 도움됨", key=f"up_{item_id}"):
            _save_feedback(item_id, 1, None)
    with col2:
        if st.button("👎 아쉬움", key=f"down_{item_id}"):
            reason = st.selectbox("사유", ["부정확", "불충분", "관련없음", "기타"], key=f"reason_{item_id}")
            _save_feedback(item_id, -1, reason)

def _save_feedback(item_id: str, rating: int, reason: str | None):
    fb_list = st.session_state.setdefault("feedbacks", [])
    fb_list.append({"item_id": item_id, "rating": rating, "reason": reason})
    st.toast("피드백 감사합니다!")
```

### 7.3 알림 발송 (선택적)

```python
# Slack Webhook URL이 설정된 경우에만 발송
# SMTP는 선택 항목으로 사이드바에서 입력

def send_slack(message: str):
    webhook_url = st.session_state.get("slack_webhook_url")
    if not webhook_url:
        return
    httpx.post(webhook_url, json={"text": message})
```

---

## 8. 기능 목록 및 세부 요건

### F-01. 외부 소스 수집 ✅ 유지 (트리거 방식 변경)

- **파일**: `pipelines/risk/collector.py`
- NVD·CISA·KrCERT CVE 피드, AWS/Azure/GCP 장애 공지, 보안 미디어 RSS 수집
- **[변경]** 자동 스케줄 → 탭1 "수집 시작" 버튼 클릭 트리거
- **[변경]** 실패 시 → `st.warning()` 화면 표시 (관리자 이메일 알림 제거)
- `st.progress()` 로 수집 진행 상태 실시간 표시
- 소스별 타임아웃 10초, 실패 소스 스킵 후 계속 진행

### F-02. 리스크 분류 및 필터링 ✅ 유지 (설정 위치 변경)

- **파일**: `pipelines/risk/rule_filter.py`
- CVSS 임계값 슬라이더 (사이드바, 기본 7.0)
- **[변경]** 필터 규칙 DB 로드 → `st.session_state["filter_config"]` 에서 읽기
- 키워드 화이트리스트·블랙리스트 텍스트 입력 (사이드바)
- 필터 후 0건 → `st.info("오늘은 관련 리스크가 없습니다.")` 표시

### F-03. LLM 리스크 요약 생성 ✅ 유지 (모델 변경)

- **파일**: `pipelines/risk/summarizer.py`
- **[변경]** Claude → GPT-4o-mini (`gpt-4o-mini`)
- **[변경]** `st.write_stream()` 으로 스트리밍 출력
- 요약 길이: 라디오 버튼 (간단/상세) → 프롬프트 동적 조정
- Critical 항목 존재 시 → `st.error()` 빨간 배너 강조

### F-04. 브리핑 실행 ✅ 유지 (스케줄→수동)

- **파일**: `pages/risk_briefing.py` (또는 탭1 내부)
- **[변경]** 자동 스케줄러 → "브리핑 생성" 버튼 수동 실행
- **[변경]** Slack 발송 → Webhook URL 설정 시 선택적 발송
- 생성된 브리핑 `session_state["briefing_history"]` 저장 (탭3 이력 확인)
- "브리핑 복사" 버튼 (`st.code()` + 클립보드 복사 지원)

### F-05. SAP 문서 인덱싱 ✅ 유지 (저장소 변경)

- **파일**: `pipelines/sap/indexer.py`
- **[변경]** pgvector → ChromaDB 인메모리 (세션 종료 시 소멸)
- **[선택]** `chromadb.PersistentClient(path="./chroma_db")` 로 로컬 파일 영속화
- 탭4 "설정" 에서 SAP 문서 URL 목록 입력 후 인덱싱 트리거
- `st.progress()` + `st.status()` 로 인덱싱 진행 표시
- 인덱싱 결과: 문서 수·청크 수 `st.metric()` 표시

### F-06. 하이브리드 검색 엔진 ✅ 유지 (엔진 변경)

- **파일**: `pipelines/sap/searcher.py`
- **[변경]** Elasticsearch → `rank_bm25` 라이브러리
- **[변경]** pgvector → ChromaDB 벡터 검색
- RRF(Reciprocal Rank Fusion) 병합 로직 동일
- 검색 점수 임계값 미달 → "관련 문서를 찾지 못했습니다" 안내

### F-07. SAP 오류·T-code Q&A ✅ 유지 (모델 변경)

- **파일**: `pipelines/sap/rag_generator.py`
- **[변경]** Claude → GPT-4o-mini
- **[변경]** `st.write_stream()` 스트리밍 답변
- 출처 URL·Note 번호 답변 내 포함 (동일)
- 신뢰도 낮음 → 면책 문구 자동 추가 (동일)

### F-08. 대화형 멀티턴 세션 ✅ 유지 (저장소 변경)

- **파일**: `core/session_manager.py`
- **[변경]** PostgreSQL → `st.session_state["chat_history"]`
- `st.chat_message()` + `st.chat_input()` Streamlit 채팅 UI 사용
- 세션 내 대화 이력 유지 (브라우저 새로고침 시 초기화)
- "대화 초기화" 버튼으로 수동 세션 리셋
- "대화 내보내기" 버튼 → Markdown 파일 다운로드 (`st.download_button`)

### F-09. 알림 채널 연동 ⚠️ 축소

- **파일**: `core/notifier.py`
- **[축소]** Slack Webhook만 지원 (Teams·SMTP는 선택적 추가)
- 사이드바에서 Slack Webhook URL 입력 시 활성화
- Critical 항목 발생 시 Slack 즉시 발송 (URL 설정된 경우)
- **[제거]** DND 시간대, 수신자 그룹 설정

### F-10. 회사 IT 컨텍스트 관리 ✅ 유지 (저장소 변경)

- **파일**: `core/context_manager.py`
- **[변경]** DB 저장 → 사이드바 UI 입력 + `context.json` 파일 저장 (선택)
- SAP 버전·클라우드·OS 멀티셀렉트 UI
- "컨텍스트 저장" → `context.json` 다운로드 버튼
- "컨텍스트 불러오기" → JSON 파일 업로드 (`st.file_uploader`)

### F-11. 의도 분류 및 라우팅 ✅ 유지

- **파일**: `agents/intent_classifier.py`
- GPT-4o-mini 기반 분류 (동일 로직)
- 신뢰도 < 0.7 → `st.warning()` 재확인 메시지
- 분류 결과 `st.session_state["routing_logs"]` 저장

### F-12. 응답 품질 피드백 ✅ 유지 (저장소 변경)

- **파일**: `core/feedback.py`
- **[변경]** DB 저장 → `st.session_state["feedbacks"]` 리스트
- 👍/👎 버튼 + 부정 사유 선택
- 탭3 대시보드에서 피드백 집계 표시
- **[제거]** 검토 큐 자동 등록, SIEM 연동

### F-13. 통합 대시보드 ✅ 유지 (프레임워크 변경)

- **파일**: `pages/dashboard.py` (또는 탭3)
- **[변경]** Next.js 차트 → `st.dataframe()` + `st.bar_chart()` + `st.metric()`
- 수집 건수·필터 후 건수·브리핑 생성 횟수 `st.metric()`
- SAP Q&A 질의 수·평균 피드백 점수 표시
- 브리핑 이력 `st.dataframe()` 테이블
- "CSV 내보내기" → `st.download_button()` (pandas DataFrame → CSV)

### F-14. 접근 제어 및 감사 로그 ❌ 제거

- **[제거]** RBAC, SSO, SIEM 연동 제거
- **[대체]** API Key 입력 방식으로 단순 인증
- API Key 미입력 시 `st.stop()` 으로 실행 중단
- API Key는 `session_state` 내에서만 유지, 파일 기록 없음

---

## 9. Streamlit 화면 구성

### 9.1 전체 레이아웃

```
┌─────────────────────────────────────────────────────┐
│  사이드바                  메인 영역                   │
│  ─────────               ──────────────────────────  │
│  🔑 API Key 입력           [탭1] 리스크 브리핑         │
│  🏢 회사 IT 환경 설정       [탭2] SAP Q&A              │
│  🔔 Slack Webhook (선택)   [탭3] 대시보드              │
│  ⚙️  필터 설정              [탭4] 설정·인덱싱           │
└─────────────────────────────────────────────────────┘
```

### 9.2 탭1 — 리스크 브리핑

```python
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("오늘의 IT 리스크 브리핑")
    with col2:
        if st.button("🔄 수집 및 브리핑 생성", type="primary"):
            with st.spinner("외부 소스 수집 중..."):
                items = collector.collect_all()
            items = dedup.filter(items)
            items = rule_filter.apply(items)
            
            if not items:
                st.info("오늘은 관련 리스크가 없습니다.")
            else:
                if any(i.severity == "Critical" for i in items):
                    st.error(f"⚠️ Critical 항목 {sum(...)}건 포함 — 즉시 확인 필요")
                
                with st.container(border=True):
                    summarizer.summarize(items, company_ctx)   # 스트리밍 출력
    
    # 이전 브리핑 이력
    if st.session_state.get("briefing_history"):
        with st.expander("브리핑 이력"):
            for b in reversed(st.session_state["briefing_history"]):
                st.markdown(f"**{b['created_at']}**")
                st.markdown(b["content"])
                st.divider()
```

### 9.3 탭2 — SAP Q&A

```python
with tab2:
    st.subheader("SAP 운영 Q&A")
    
    # 채팅 이력 표시
    for msg in st.session_state.get("chat_history", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                render_feedback(msg["id"])
    
    # 입력
    if prompt := st.chat_input("오류 메시지 또는 T-code를 입력하세요..."):
        # 처리 및 스트리밍 답변 출력
        ...
    
    # 세션 초기화
    if st.button("대화 초기화"):
        st.session_state["chat_history"] = []
        st.rerun()
```

### 9.4 탭4 — 설정·인덱싱

```python
with tab4:
    st.subheader("SAP 문서 인덱싱")
    
    default_urls = [
        "https://help.sap.com/docs/...",
        "https://community.sap.com/...",
    ]
    urls_input = st.text_area("인덱싱할 SAP 문서 URL (줄 구분)", "\n".join(default_urls))
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("인덱싱 시작", type="primary"):
            urls = [u.strip() for u in urls_input.split("\n") if u.strip()]
            with st.status("인덱싱 중...", expanded=True) as status:
                for i, url in enumerate(urls):
                    st.write(f"처리 중: {url}")
                    indexer.index_url(url)
                    st.progress((i+1) / len(urls))
                status.update(label="인덱싱 완료!", state="complete")
    with col2:
        col = get_chroma_collection()
        st.metric("인덱싱된 청크 수", col.count())
```

---

## 10. 데이터 모델 (인메모리·파일 기반)

### 10.1 `st.session_state` 키 목록

| 키 | 타입 | 설명 |
|---|---|---|
| `openai_api_key` | `str` | 사용자 입력 API Key |
| `company_context` | `dict` | 회사 IT 환경 설정 |
| `filter_config` | `dict` | 필터 설정 (CVSS·키워드) |
| `slack_webhook_url` | `str` | Slack Webhook URL (선택) |
| `seen_hashes` | `set` | 수집 중복 제거용 해시 집합 |
| `briefing_history` | `list[dict]` | 브리핑 이력 |
| `chat_history` | `list[dict]` | SAP Q&A 대화 이력 |
| `feedbacks` | `list[dict]` | 피드백 누적 리스트 |
| `routing_logs` | `list[dict]` | 의도 분류 로그 |
| `chroma_client` | `ChromaClient` | ChromaDB 인스턴스 |

### 10.2 선택적 파일 저장

```
project-root/
├── context.json          # 회사 컨텍스트 (사용자 저장 선택)
├── chroma_db/            # ChromaDB 영속 디렉터리 (선택)
└── briefing_export.md    # 브리핑 내보내기 (다운로드)
```

---

## 11. 디렉터리 구조

```
project-root/
├── streamlit_app.py              # 진입점 (st.set_page_config, 탭 구성)
├── requirements.txt
├── .env.example                  # (선택) 기본값 제공용 — API Key 미포함
│
├── agents/
│   └── intent_classifier.py      # F-11 의도 분류 (GPT-4o-mini)
│
├── pipelines/
│   ├── risk/
│   │   ├── collector.py          # F-01 RSS/API 수집
│   │   ├── dedup.py              # F-01 session_state 중복 제거
│   │   ├── rule_filter.py        # F-02 룰 필터
│   │   └── summarizer.py         # F-03 GPT-4o-mini 요약
│   └── sap/
│       ├── indexer.py            # F-05 ChromaDB 인덱싱
│       ├── preprocessor.py       # F-07 입력 전처리
│       ├── searcher.py           # F-06 BM25 + ChromaDB 검색
│       └── rag_generator.py      # F-07 GPT-4o-mini RAG 답변
│
├── core/
│   ├── context_manager.py        # F-10 컨텍스트 관리
│   ├── session_manager.py        # F-08 session_state 세션
│   ├── feedback.py               # F-12 피드백 UI
│   └── notifier.py               # F-09 Slack Webhook (선택)
│
└── tests/
    ├── test_rule_filter.py
    ├── test_hybrid_searcher.py
    └── test_intent_classifier.py
```

### 11.1 실행 방법

```bash
# 설치
pip install -r requirements.txt

# 실행
streamlit run streamlit_app.py

# 브라우저에서 http://localhost:8501 접속
# 사이드바에서 OpenAI API Key 입력 후 사용
```

---

## 12. 구현 우선순위 및 단계

### Phase 1 — MVP (1~2주, Streamlit 단독)

> 목표: 핵심 기능 동작 확인, 데모 가능 수준

- [ ] `streamlit_app.py` 기본 구조 (사이드바 + 4탭)
- [ ] API Key 사이드바 입력 + `st.stop()` 가드
- [ ] 회사 컨텍스트 사이드바 설정 (F-10)
- [ ] F-01 피드 수집 (주요 3개 소스)
- [ ] F-02 룰 필터 (CVSS 슬라이더)
- [ ] F-03 GPT-4o-mini 리스크 요약 (스트리밍)
- [ ] F-05 SAP 문서 ChromaDB 인덱싱
- [ ] F-06 하이브리드 검색
- [ ] F-07 SAP Q&A RAG 답변 (스트리밍)
- [ ] F-08 `st.session_state` 멀티턴 채팅 UI

### Phase 2 — 고도화 (1~2주)

- [ ] F-11 의도 분류 + 크로스 파이프라인
- [ ] F-12 피드백 버튼
- [ ] F-13 탭3 대시보드 (st.metric + st.dataframe)
- [ ] F-09 Slack Webhook 선택적 연동
- [ ] 컨텍스트 JSON 저장/불러오기 (F-10)
- [ ] 대화·브리핑 내보내기 (`st.download_button`)

### Phase 3 — 안정화 (이후)

- [ ] ChromaDB 영속화 (재시작 후에도 인덱스 유지)
- [ ] APScheduler 백그라운드 자동 수집
- [ ] 단위 테스트 커버리지 80%
- [ ] (선택) FastAPI 분리 + Streamlit 프론트만 유지

---

## 13. 테스트 요건

### 13.1 단위 테스트

```python
# tests/test_rule_filter.py
def test_cvss_threshold():
    items = [RawFeedItem(cvss_score=9.8, ...), RawFeedItem(cvss_score=5.0, ...)]
    result = RuleFilter(min_cvss=7.0).apply(items)
    assert len(result) == 1
    assert result[0].cvss_score == 9.8

# tests/test_intent_classifier.py  (모킹 사용)
@patch("agents.intent_classifier.call_llm")
def test_sap_intent(mock_llm):
    mock_llm.return_value = '{"intent": "sap_qa", "confidence": 0.95}'
    result = IntentClassifier().classify("SM21 오류 해결법")
    assert result.intent == "sap_qa"

# tests/test_dedup.py
def test_duplicate_removal():
    # session_state 모킹 필요
    ...
```

### 13.2 Streamlit 테스트

- `streamlit.testing.v1.AppTest` 사용
- 탭 전환, 버튼 클릭, 채팅 입력 시나리오 테스트
- API Key 미입력 시 `st.stop()` 동작 확인

---

## 14. 비기능 요건

| 항목 | v1.0 요건 | v2.0 요건 (Streamlit) | 비고 |
|---|---|---|---|
| SAP Q&A 응답 시간 | 5초 이내 (P95) | 10초 이내 허용 | 단일 사용자 시나리오 |
| 브리핑 생성 시간 | 60초 이내 | 90초 이내 허용 | 스트리밍으로 체감 단축 |
| 동시 세션 수 | 50 세션 | 단일 사용자 (1~3) | Streamlit 기본 구조 |
| 데이터 영속성 | PostgreSQL 영구 | 세션 내 / 선택적 파일 | 재시작 시 초기화 |
| API Key 보안 | 환경 변수 | `type="password"` + session_state | 파일 저장 금지 |
| 설치 복잡도 | Docker 필요 | `pip install` 후 즉시 실행 | 진입 장벽 최소화 |
| LLM 호출 실패 | 재시도 3회 | `st.error()` + 재시도 버튼 | 사용자 수동 재시도 |

---

*본 명세서는 v2.0 Streamlit 전환 기준입니다. 향후 프로덕션 전환 시 v1.0 아키텍처(FastAPI + PostgreSQL + Redis)로 마이그레이션을 권장합니다.*
