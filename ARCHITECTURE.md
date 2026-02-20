# AI Agent Chatbot: 아키텍처 개요

> LangGraph 기반 멀티 에이전트 챗봇 - 시스템 설계

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                          클라이언트 레이어                            │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Next.js 16 + TypeScript + Zustand + shadcn/ui              │   │
│   └─────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ HTTPS (REST + SSE)
┌─────────────────────────────▼───────────────────────────────────────┐
│                          API 게이트웨이                              │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  FastAPI (Python 3.12+)                                     │   │
│   │  - CORS / Exception / Logging Middleware                    │   │
│   │  - REST API + SSE Streaming                                 │   │
│   └─────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                        오케스트레이션 레이어                          │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  LangGraph StateGraph                                       │   │
│   │  ┌──────────┐  ┌──────┐  ┌─────────┐  ┌────────┐  ┌─────┐  │   │
│   │  │Supervisor│─▶│ Chat │  │   RAG   │  │  Web   │  │Code │  │   │
│   │  │ (Router) │  │      │  │ (Docs)  │  │ Search │  │     │  │   │
│   │  └──────────┘  └──────┘  └─────────┘  └────────┘  └─────┘  │   │
│   └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                        인프라스트럭처 레이어                          │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐                     │
│   │  Pinecone  │  │   Redis    │  │  Supabase  │                     │
│   │ (Vector DB)│  │  (Session) │  │(Auth + DB) │                     │
│   └────────────┘  └────────────┘  └────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| **프론트엔드** | Next.js + TypeScript | 16.x |
| **백엔드** | FastAPI + Python | 3.12 |
| **AI 오케스트레이션** | LangGraph + LangChain | 0.2.x |
| **LLM** | OpenRouter | Gemini/GPT-4o/Claude |
| **Vector DB** | Pinecone | - |
| **임베딩** | multilingual-e5-large | - |
| **세션 메모리** | Upstash Redis / In-Memory | - |
| **인증** | Supabase | - |
| **배포** | Render + Vercel | - |

---

## 백엔드 아키텍처

### 디렉토리 구조

```
backend/src/
├── agents/              # 멀티 에이전트 시스템
│   ├── supervisor.py    # Supervisor (라우팅)
│   ├── chat_agent.py    # 일반 대화 + 메모리 명령
│   ├── code_agent.py    # 코드 생성/실행
│   ├── rag_agent.py     # 문서 기반 Q&A
│   └── web_search_agent.py  # 웹 검색
│
├── api/                 # REST API
│   ├── routes.py        # 엔드포인트 정의
│   ├── schemas.py       # Pydantic 모델
│   └── middleware.py    # 미들웨어
│
├── core/                # 핵심 모듈
│   ├── config.py        # 설정
│   ├── di_container.py  # DI 컨테이너
│   ├── protocols.py     # Protocol 인터페이스
│   ├── prompt_security.py  # 프롬프트 인젝션 탐지
│   └── logging.py       # 구조화 로깅
│
├── documents/           # 문서 처리 (RAG)
│   ├── parser.py        # 다중 포맷 파서
│   ├── chunker.py       # 구조 인식 청커
│   ├── pinecone_store.py   # Pinecone 벡터 스토어
│   └── retriever_impl.py   # 문서 검색
│
├── graph/               # LangGraph 상태 머신
│   ├── builder.py       # 그래프 빌드
│   ├── state.py         # AgentState TypedDict
│   └── edges.py         # 조걶부 라우팅
│
├── llm/                 # LLM 프로바이더
│   ├── factory.py       # LLMFactory
│   ├── openai_provider.py
│   └── anthropic_provider.py
│
├── memory/              # 메모리 시스템
│   ├── in_memory_store.py   # 개발용
│   ├── redis_store.py       # 프로덕션용
│   └── long_term_memory.py  # 장기 메모리
│
└── tools/               # 에이전트 도구
    ├── web_search.py    # Tavily 웹 검색
    ├── code_executor.py # Python 실행
    └── retriever.py     # 문서 검색 도구
```

### Protocol 인터페이스

| Protocol | 메서드 | 설명 |
|----------|--------|------|
| `LLMProvider` | `generate()`, `stream()` | LLM 추상화 |
| `MemoryStore` | `get_messages()`, `add_message()` | 대화 메모리 |
| `DocumentRetriever` | `retrieve()`, `add_documents()` | RAG 검색 |
| `Tool` | `name`, `description`, `execute()` | 에이전트 도구 |

### 에이전트 시스템

| 에이전트 | 역할 | 주요 기능 |
|----------|------|----------|
| **Supervisor** | 라우팅 | 사용자 쿼리 분석 → 적절한 에이전트 선택 |
| **ChatAgent** | 일반 대화 | 메모리 명령, 사용자 프로파일링 |
| **CodeAgent** | 코드 | 코드 생성/설명/디버깅 |
| **RAGAgent** | 문서 Q&A | 문서 검색 + 컨텍스트 기반 답변 |
| **WebSearchAgent** | 웹 검색 | Tavily API로 실시간 검색 |

**메모리 명령**:
- `기억해:` / `기억해줘:` - 사용자 정보 저장
- `알고 있니?` - 저장된 메모리 검색
- `잊어줘:` - 메모리 삭제
- `요약해줘` - 대화 요약

### API 엔드포인트

| Method | Path | Auth | 설명 |
|--------|------|------|------|
| POST | `/api/v1/chat` | ❌ | 동기 채팅 |
| POST | `/api/v1/chat/stream` | ❌ | SSE 스트리밍 채팅 |
| POST | `/api/v1/documents/upload` | ✅ | 파일 업로드 |
| GET | `/api/v1/documents` | ✅ | 문서 목록 |
| GET | `/api/v1/sessions` | ✅ | 세션 목록 |
| DELETE | `/api/v1/sessions/{id}` | ❌ | 세션 삭제 |
| GET | `/api/v1/health` | ❌ | 헬스 체크 |

---

## 프론트엔드 아키텍처

### 디렉토리 구조

```
frontend/src/
├── app/                 # App Router
│   ├── layout.tsx       # 루트 레이아웃
│   └── chat/page.tsx    # 채팅 페이지
│
├── components/
│   ├── chat/            # 채팅 UI
│   │   ├── chat-container.tsx
│   │   ├── chat-input.tsx
│   │   ├── message-list.tsx
│   │   └── markdown-renderer.tsx
│   ├── documents/       # 문서 업로드 UI
│   ├── sidebar/         # 세션 사이드바
│   └── ui/              # shadcn/ui 컴포넌트
│
├── stores/              # Zustand 스토어
│   ├── chat-store.ts    # 채팅 상태
│   ├── auth-store.ts    # 인증 상태
│   └── document-store.ts  # 문서 상태
│
└── lib/                 # 유틸리티
    ├── api.ts           # API 클라이언트
    ├── sse.ts           # SSE 스트리밍
    └── token-manager.ts # JWT 토큰 관리
```

### 상태 관리 (Zustand)

| 스토어 | 상태 | 설명 |
|--------|------|------|
| **ChatStore** | sessions, messages, streaming | 채팅 상태, localStorage 영속화 |
| **AuthStore** | user, isAuthenticated, tokens | 인증 상태, 자동 토큰 갱신 |
| **DocumentStore** | documents, uploadStatus | 문서 업로드 상태 |

### SSE 스트리밍 파이프라인

```
사용자 입력
    ↓
ChatStore.sendMessage()
    ↓
POST /api/v1/chat/stream
    ↓
EventSource (fetch + ReadableStream)
    ↓
이벤트 파싱: metadata | token | agent | done | error
    ↓
상태 업데이트 → UI 리렌더
```

---

## 데이터 흐름도

### 채팅 요청

```
Client
    │ POST /api/v1/chat {message, session_id}
    ▼
detect_injection(message)
    ▼
create_initial_state(message, session_id)
    ▼
graph.ainvoke(state, config)
    ▼
supervisor.process(state)
    ▼
route_by_next_agent(state)
    ▼
{chat|code|rag|web_search}.process(state)
    ▼
filter_llm_output(response)
    ▼
ChatResponse 반환
```

### 문서 업로드 (RAG 파이프라인)

```
Client
    │ POST /api/v1/documents/upload
    ▼
validate_file_upload(file)
    │ 매직 바이트, MIME, 확장자 검증
    ▼
DocumentParser.parse_from_bytes(file)
    │ PDF, DOCX, TXT, MD, CSV, JSON
    ▼
DomainAwareChunker.chunk(sections)
    │ 500 토큰 max, 50 토큰 overlap
    ▼
PineconeVectorStore.add_document(chunks)
    │ 임베딩 생성 (multilingual-e5-large)
    ▼
FileUploadResponse 반환
```

---

## 메모리 시스템

### 단기 메모리 (Session Memory)

| 구현체 | 용도 | 특징 |
|--------|------|------|
| **InMemoryStore** | 개발/테스트 | dict 기반 |
| **RedisStore** | 프로덕션 | Upstash Redis, TTL 기반 |

### 장기 메모리 (Long-term Memory)

| 테이블 | 용도 |
|--------|------|
| `user_profiles` | 사용자 프로필 및 선호도 |
| `topic_summaries` | 대화 토픽 요약 |
| `user_facts` | 사용자에 대한 개별 팩트 |

### 자동 요약 트리거

- 토큰 수 > 2000
- 메시지 수 > 20
- 마지막 요약 후 10분 경과

---

## 문서 처리 파이프라인

### 파서

| 포맷 | 라이브러리 | 특징 |
|------|-----------|------|
| PDF | pdfplumber | 텍스트 + 테이블 추출 |
| DOCX | python-docx | 헤딩, 테이블 지원 |
| TXT | - | 문단 분리 |
| MD | - | 헤딩, 코드 블록 보존 |
| CSV | - | 헤더 매핑, 행별 처리 |
| JSON | - | 재귀적 키-값 추출 |

### 청커

| 전략 | 용도 | 특징 |
|------|------|------|
| default | 일반 텍스트 | 500 토큰 max, 50 토큰 overlap |
| code | 소스 코드 | 코드 블록 보존 |
| tabular | 표 데이터 | 행 단위 처리 |

---

## 애플리케이션 보안

### 입력 보안

`backend/src/core/prompt_security.py`

**프롬프트 인젝션 탐지**:
- JAILBREAK: 시스템 프롬프트 우회 시도
- DATA_EXFILTRATION: 데이터 탈취 시도
- PRIVILEGE_ESCALATION: 권한 상승 시도
- TOOL_MANIPULATION: 도구 조작 시도
- PROMPT_LEAK: 프롬프트 유출 시도

### 파일 업로드 보안

`backend/src/core/validators.py`

- 매직 바이트 검증 (PDF: `%PDF`, DOCX: `PK`)
- MIME 타입 일치 확인
- 파일 크기 제한 (10MB)
- PII 탐지 (이메일, 전화번호 등)

---

## 설계 패턴

### 1. Protocol 지향 아키텍처

```python
@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, messages: list[dict], **kwargs) -> str: ...

# 상속 없이 구현 가능
class OpenAIProvider:
    async def generate(self, messages, **kwargs) -> str: ...
```

### 2. Factory 패턴

```python
@LLMFactory.register("openai")
class OpenAIProvider: ...

llm = LLMFactory.create(config.llm)  # 자동 매핑
```

### 3. 의존성 주입

```python
@router.post("/chat")
@inject
async def chat(
    request: ChatRequest,
    graph=Depends(Provide[DIContainer.graph]),
) -> ChatResponse: ...
```

---

*최종 업데이트: 2026-02-20*
