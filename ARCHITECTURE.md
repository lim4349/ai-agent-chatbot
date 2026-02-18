# AI Agent Chatbot: 아키텍처 기술 개요

> LangGraph 기반 멀티 에이전트 챗봇 - 프로덕션 아키텍처

---

## 목차

1. [시스템 아키텍처 개요](#1-시스템-아키텍처-개요)
2. [백엔드 아키텍처](#2-백엔드-아키텍처)
3. [프론트엔드 아키텍처](#3-프론트엔드-아키텍처)
4. [데이터 흐름도](#4-데이터-흐름도)
5. [메모리 시스템](#5-메모리-시스템)
6. [문서 처리 파이프라인](#6-문서-처리-파이프라인)
7. [애플리케이션 보안](#7-애플리케이션-보안)
8. [인프라 & 배포](#8-인프라--배포)
9. [설계 패턴](#9-설계-패턴)

---

## 1. 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                          클라이언트 레이어                            │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Next.js 16 + TypeScript + Zustand + shadcn/ui              │   │
│   │  (App Router, React 19, Server Components)                  │   │
│   └─────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ HTTPS (REST + SSE)
┌─────────────────────────────▼───────────────────────────────────────┐
│                          API 게이트웨이                              │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  FastAPI (Python 3.12+)                                     │   │
│   │  - CORS Middleware                                          │   │
│   │  - ExceptionHandler Middleware                              │   │
│   │  - RequestLogging Middleware                                │   │
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
│   ┌────────────┐  ┌────────────┐  ┌────────────┐                    │
│   │   OpenAI   │  │ Anthropic  │  │   Ollama   │                    │
│   │   (LLM)    │  │   (LLM)    │  │  (Local)   │                    │
│   └────────────┘  └────────────┘  └────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

> **참고**: 인프라 보안(SSL/TLS, DDoS, WAF, CDN Rate Limiting)은 Vercel/Render가 자동 처리

### 기술 스택 요약

| 레이어 | 기술 | 버전 |
|--------|------|------|
| **프론트엔드** | Next.js + TypeScript | 16.x |
| **백엔드** | FastAPI + Python | 3.12 |
| **AI 오케스트레이션** | LangGraph + LangChain | 0.2.x |
| **LLM** | OpenAI / Anthropic | GPT-4o / Claude |
| **Vector DB** | Pinecone | - |
| **임베딩** | Pinecone Inference (multilingual-e5-large) | - |
| **세션 메모리** | Upstash Redis (프로덕션) / In-Memory (로컬) | - |
| **장기 메모리** | Supabase PostgreSQL (프로덕션) / In-Memory (로컬) | - |
| **인증** | Supabase | - |
| **웹 검색** | Tavily API | - |
| **배포** | Render (백엔드) + Vercel (프론트엔드) | - |

---

## 2. 백엔드 아키텍처

### 2.1 디렉토리 구조

```
backend/src/
├── agents/                    # 멀티 에이전트 시스템
│   ├── base.py               # BaseAgent ABC
│   ├── factory.py            # AgentFactory
│   ├── supervisor.py         # Supervisor (라우팅)
│   ├── chat_agent.py         # 일반 대화 + 메모리 명령
│   ├── code_agent.py         # 코드 생성/실행
│   ├── rag_agent.py          # 문서 기반 Q&A
│   └── web_search_agent.py   # 웹 검색
│
├── api/                       # REST API
│   ├── routes.py             # 엔드포인트 정의
│   ├── schemas.py            # Pydantic 모델
│   ├── middleware.py         # 미들웨어
│   └── dependencies.py       # FastAPI 의존성
│
├── auth/                      # 인증
│   ├── supabase_client.py    # Supabase Auth 클라이언트
│   ├── dependencies.py       # get_current_user
│   └── schemas.py            # User 모델
│
├── core/                      # 핵심 모듈
│   ├── config.py             # Pydantic Settings
│   ├── di_container.py       # DI 컨테이너 (dependency-injector)
│   ├── protocols.py          # Protocol 인터페이스
│   ├── prompt_security.py    # 프롬프트 인젝션 탐지
│   ├── validators.py         # 입력 검증
│   ├── logging.py            # 구조화 로깅 (structlog)
│   ├── auto_summarize.py     # 자동 요약
│   ├── user_profiler.py      # 사용자 프로파일링
│   └── topic_memory.py       # 토픽 메모리
│
├── documents/                 # 문서 처리
│   ├── parser.py             # 다중 포맷 파서
│   ├── chunker.py            # 구조 인식 청커
│   ├── pinecone_store.py     # Pinecone 벡터 스토어
│   ├── embeddings.py         # 임베딩 생성
│   ├── retriever_impl.py     # 문서 검색
│   └── chunking/             # 도메인별 청킹 전략
│
├── graph/                     # LangGraph 상태 머신
│   ├── builder.py            # 그래프 빌드
│   ├── state.py              # AgentState TypedDict
│   └── edges.py              # 조건부 라우팅
│
├── llm/                       # LLM 프로바이더
│   ├── factory.py            # LLMFactory
│   ├── openai_provider.py    # OpenAI
│   ├── anthropic_provider.py # Anthropic
│   └── ollama_provider.py    # Ollama (로컬)
│
├── memory/                    # 메모리 시스템
│   ├── factory.py            # MemoryStoreFactory
│   ├── in_memory_store.py    # 개발용
│   ├── redis_store.py        # 프로덕션용
│   ├── long_term_memory.py   # Supabase/InMemory
│   └── memory_weights.py     # 가중치 기반 필터링
│
├── tools/                     # 에이전트 도구
│   ├── registry.py           # ToolRegistry
│   ├── web_search.py         # Tavily 웹 검색
│   ├── code_executor.py      # Python 실행
│   ├── retriever.py          # 문서 검색 도구
│   ├── memory_tool.py        # 메모리 검색 도구
│   └── mcp/                  # MCP 서버 통합
│
└── main.py                    # FastAPI 진입점
```

### 2.2 Protocol 인터페이스

`backend/src/core/protocols.py`

| Protocol | 메서드 | 설명 |
|----------|--------|------|
| `LLMProvider` | `generate()`, `stream()`, `generate_structured()` | LLM 추상화 |
| `MemoryStore` | `get_messages()`, `add_message()`, `clear()`, `add_summary()`, `get_summary()` | 대화 메모리 |
| `DocumentRetriever` | `retrieve()`, `add_documents()` | RAG 검색 |
| `Tool` | `name`, `description`, `execute()` | 에이전트 도구 |
| `DocumentParser` | `parse_from_bytes()`, `parse()` | 문서 파싱 |
| `DocumentChunker` | `chunk()` | 문서 청킹 |
| `Summarizer` | `summarize()` | 대화 요약 |
| `UserProfiler` | `extract_profile()`, `get_profile()` | 사용자 프로파일 |
| `TopicMemory` | `extract_topics()`, `get_related_sessions()` | 토픽 추적 |
| `MemoryTool` | `name`, `description`, `execute()` | 메모리 검색 |

### 2.3 DI 컨테이너

`backend/src/core/di_container.py`

**dependency-injector** 라이브러리 사용:

```python
class DIContainer(containers.DeclarativeContainer):
    # Singleton
    config = providers.Singleton(get_config)
    llm = providers.Singleton(_create_llm, config=config.provided.llm)
    memory = providers.Singleton(_create_memory, config=config.provided.memory)
    embedding_generator = providers.Singleton(_create_embedding_generator, config=config)
    vector_store = providers.Singleton(_create_vector_store, config=config)
    retriever = providers.Singleton(_create_retriever, vector_store=vector_store, config=config)
    long_term_memory = providers.Singleton(_create_long_term_memory, config=config)
    tool_registry = providers.Singleton(_create_tool_registry, config=config, retriever=retriever)
    graph = providers.Singleton(_create_graph_factory)

    # Factory
    summarizer = providers.Factory(_create_summarizer, config=config, llm=llm, memory=memory)
    user_profiler = providers.Factory(_create_user_profiler, config=config, long_term_memory=long_term_memory)
    topic_memory = providers.Factory(_create_topic_memory, config=config, long_term_memory=long_term_memory)
    memory_tool = providers.Factory(_create_memory_tool, memory=memory, embedding_generator=embedding_generator)
    document_parser = providers.Factory(_create_document_parser)
    document_chunker = providers.Factory(_create_document_chunker, config=config)
```

### 2.4 LangGraph 상태 머신

`backend/src/graph/state.py`

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]  # 메시지 누적
    next_agent: str | None                    # 라우팅 대상
    tool_results: list[dict]                  # 도구 실행 결과
    metadata: dict                            # session_id, user_id, routing_info 등
```

`backend/src/graph/builder.py`

```
그래프 흐름:
START → supervisor → route_by_next_agent → {chat | code | rag | web_search} → END

- rag, web_search는 조건부 노드 (설정에 따라 추가/제거)
- MemorySaver로 상태 영속화
```

### 2.5 에이전트 시스템

| 에이전트 | 역할 | 주요 기능 |
|----------|------|----------|
| **Supervisor** | 라우팅 | 사용자 쿼리 분석 → 적절한 에이전트 선택 |
| **ChatAgent** | 일반 대화 | 메모리 명령, 사용자 프로파일링, 토픽 메모리 |
| **CodeAgent** | 코드 | 코드 생성/설명/디버깅, 선택적 실행 |
| **RAGAgent** | 문서 Q&A | 문서 검색 + 컨텍스트 기반 답변 |
| **WebSearchAgent** | 웹 검색 | Tavily API로 실시간 검색 |

**메모리 명령 (ChatAgent)**:
- `기억해:` / `기억해줘:` - 사용자 정보 저장
- `알고 있니?` - 저장된 메모리 검색
- `잊어줘:` - 메모리 삭제
- `요약해줘` - 대화 요약

### 2.6 API 엔드포인트

`backend/src/api/routes.py`

| Method | Path | Auth | 설명 |
|--------|------|------|------|
| POST | `/api/v1/chat` | ❌ | 동기 채팅 |
| POST | `/api/v1/chat/stream` | ❌ | SSE 스트리밍 채팅 |
| GET | `/api/v1/health` | ❌ | 헬스 체크 |
| GET | `/api/v1/agents` | ❌ | 에이전트 목록 |
| POST | `/api/v1/documents/upload` | ✅ | 파일 업로드 |
| GET | `/api/v1/documents` | ✅ | 문서 목록 |
| DELETE | `/api/v1/documents/{id}` | ✅ | 문서 삭제 |
| POST | `/api/v1/sessions` | ✅ | 세션 생성 |
| GET | `/api/v1/sessions` | ✅ | 세션 목록 |
| DELETE | `/api/v1/sessions/{id}` | ❌ | 세션 메모리 삭제 |
| DELETE | `/api/v1/sessions/{id}/full` | ✅ | 세션 + 문서 전체 삭제 |
| GET | `/api/v1/logs` | ❌ | 로그 조회 |
| DELETE | `/api/v1/logs` | ❌ | 로그 삭제 |

---

## 3. 프론트엔드 아키텍처

### 3.1 디렉토리 구조

```
frontend/src/
├── app/                       # App Router
│   ├── layout.tsx            # 루트 레이아웃
│   ├── page.tsx              # 홈
│   └── chat/page.tsx         # 채팅 페이지
│
├── components/
│   ├── auth/                 # 인증 컴포넌트
│   ├── chat/                 # 채팅 UI
│   │   ├── chat-container.tsx
│   │   ├── chat-input.tsx
│   │   ├── message-list.tsx
│   │   ├── message-bubble.tsx
│   │   ├── markdown-renderer.tsx
│   │   ├── typing-indicator.tsx
│   │   ├── agent-badge.tsx
│   │   └── memory-*.tsx      # 메모리 관련 컴포넌트
│   ├── documents/            # 문서 업로드 UI
│   ├── sidebar/              # 세션 사이드바
│   ├── header/               # 헤더 + 헬스 인디케이터
│   └── ui/                   # shadcn/ui 컴포넌트
│
├── stores/                    # Zustand 스토어
│   ├── chat-store.ts         # 채팅 상태
│   ├── auth-store.ts         # 인증 상태
│   ├── document-store.ts     # 문서 상태
│   └── toast-store.ts        # 알림
│
├── lib/                       # 유틸리티
│   ├── api.ts                # API 클라이언트
│   ├── sse.ts                # SSE 스트리밍
│   ├── token-manager.ts      # JWT 토큰 관리
│   ├── security-validator.ts # 입력 검증
│   └── file-validation.ts    # 파일 검증
│
└── types/                     # TypeScript 타입
    └── index.ts
```

### 3.2 상태 관리 (Zustand)

| 스토어 | 상태 | 설명 |
|--------|------|------|
| **ChatStore** | sessions, messages, streaming, isSidebarOpen | 채팅 상태, localStorage 영속화 |
| **AuthStore** | user, isAuthenticated, tokens | 인증 상태, 자동 토큰 갱신 |
| **DocumentStore** | documents, uploadStatus | 문서 업로드 상태 |
| **ToastStore** | notifications | 알림 큐 |

### 3.3 SSE 스트리밍 파이프라인

`frontend/src/lib/sse.ts`

```
사용자 입력
    ↓
ChatStore.sendMessage()
    ↓
POST /api/v1/chat/stream (Authorization: Bearer <token>)
    ↓
EventSource (fetch + ReadableStream)
    ↓
이벤트 파싱: metadata | token | agent | done | error
    ↓
토큰 버퍼링 (50ms flush, 100자 임계값)
    ↓
fixSentenceSpacing() [LLM 후처리]
    ↓
상태 업데이트 → UI 리렌더
```

### 3.4 인증 흐름

```
로그인 요청 (Supabase)
    ↓
JWT 토큰 발급 (access_token, refresh_token)
    ↓
tokenManager.setToken() → sessionStorage / localStorage
    ↓
API 요청 시 Authorization 헤더 자동 추가
    ↓
401 응답 시 자동 토큰 갱신 (5분 전)
    ↓
갱신 실패 시 로그아웃
```

---

## 4. 데이터 흐름도

### 4.1 채팅 요청 (동기)

```
Client
    │ POST /api/v1/chat {message, session_id}
    ▼
detect_injection(message)
    │ 프롬프트 인젝션 탐지
    ▼
sanitize_for_llm(message)
    │ 입력 새니타이징
    ▼
create_initial_state(message, session_id)
    │ AgentState 생성
    ▼
graph.ainvoke(state, config)
    │ LangGraph 실행
    ▼
supervisor.process(state)
    │ 쿼리 분석 → next_agent 결정
    ▼
route_by_next_agent(state)
    │ 조건부 라우팅
    ▼
{chat|code|rag|web_search}.process(state)
    │ 전문 에이전트 실행
    ▼
filter_llm_output(response)
    │ 프롬프트 유출 필터링
    ▼
ChatResponse 반환
```

### 4.2 채팅 스트리밍 (SSE)

```
Client
    │ POST /api/v1/chat/stream
    ▼
EventSourceResponse
    │ SSE 연결 설정
    ▼
graph.astream_events(state, config)
    │ 스트리밍 모드 실행
    ▼
이벤트 yield:
    ├── event: metadata → {"session_id": "...", "agent": "..."}
    ├── event: token → {"content": "..."}
    ├── event: agent → {"from": "supervisor", "to": "chat"}
    ├── event: done → {"message": "Complete"}
    └── event: error → {"error": "..."}
```

### 4.3 문서 업로드 (RAG 파이프라인)

```
Client
    │ POST /api/v1/documents/upload (multipart/form-data)
    ▼
validate_file_upload(file)
    │ 매직 바이트, MIME, 확장자 검증
    ▼
DocumentParser.parse_from_bytes(file)
    │ 포맷별 파싱 (PDF, DOCX, TXT, MD, CSV, JSON)
    │ 한국어 인코딩 감지 (UTF-8 → CP949 → EUC-KR → Latin-1)
    ▼
DomainAwareChunker.chunk(sections)
    │ 구조 인식 청킹 (default | code | tabular)
    │ 500 토큰 max, 50 토큰 overlap
    ▼
PineconeVectorStore.add_document(chunks)
    │ 임베딩 생성 (Pinecone Inference API)
    │ 네임스페이스: user_{user_id}
    ▼
FileUploadResponse 반환
```

### 4.4 인증

```
Client
    │ Supabase 로그인
    ▼
Supabase Auth API
    │ JWT 발급
    ▼
tokenManager.setToken(access_token, refresh_token)
    │ 저장소 선택: sessionStorage (기본) / localStorage (remember me)
    ▼
API 요청
    │ Authorization: Bearer <access_token>
    ▼
Backend: get_current_user()
    │ SupabaseAuthClient.verify_token()
    ▼
User 객체 반환
    │ id, email, metadata
```

---

## 5. 메모리 시스템

### 5.1 단기 메모리 (Session Memory)

| 구현체 | 용도 | 특징 |
|--------|------|------|
| **InMemoryStore** | 개발/테스트 | dict 기반, 서버 재시작 시 데이터 유실 |
| **RedisStore** | 프로덕션 | Upstash Redis, TTL 기반 자동 만료 |

```python
# RedisStore 주요 기능
- 메시지: Redis List (FIFO, TTL)
- 요약: Redis Key (TTL × 2로 더 오래 보관)
- get_messages_with_limit(): 토큰 제한 기반 조회
```

### 5.2 장기 메모리 (Long-term Memory)

Supabase PostgreSQL 기반 (프로덕션), In-Memory (로컬 개발):

| 테이블 | 용도 |
|--------|------|
| `user_profiles` | 사용자 프로필 및 선호도 |
| `topic_summaries` | 대화 토픽 요약 |
| `user_facts` | 사용자에 대한 개별 팩트 |

### 5.3 자동 요약

`backend/src/core/auto_summarize.py`

**트리거 조건**:
- 토큰 수 > 2000
- 메시지 수 > 20
- 마지막 요약 후 10분 경과

### 5.4 메모리 가중치

`backend/src/memory/memory_weights.py`

| 팩터 | 가중치 | 설명 |
|--------|--------|------|
| LENGTH | +0.1/100자 (max 0.3) | 긴 메시지일수록 중요 |
| CODE | +0.2 | 코드 블록 포함 |
| QUESTION | +0.15 | 질문 포함 |
| EMPHASIS | +0.15 | 강조 표시 (!!, ??, CAPS) |

### 5.5 메모리 명령

한국어 명령어 지원 (ChatAgent):

| 명령 | 예시 | 동작 |
|------|------|------|
| 기억해 | `기억해: 나는 커피를 좋아해` | LongTermMemory에 저장 |
| 알고 있니? | `내가 좋아하는 게 뭐야?` | 메모리 검색 |
| 잊어줘 | `잊어줘: 커피` | 메모리 삭제 |
| 요약해줘 | `지금까지 대화 요약해줘` | 즉시 요약 생성 |

---

## 6. 문서 처리 파이프라인

### 6.1 파서

`backend/src/documents/parser.py`

| 포맷 | 라이브러리 | 특징 |
|------|-----------|------|
| PDF | pdfplumber | 텍스트 + 테이블 추출 |
| DOCX | python-docx | 헤딩, 테이블 지원 |
| TXT | - | 문단 분리 |
| MD | - | 헤딩, 코드 블록 보존 |
| CSV | - | 헤더 매핑, 행별 처리 |
| JSON | - | 재귀적 키-값 추출 |

**출력**: `DocumentSection(content, page, heading, section_type)`

### 6.2 청커

`backend/src/documents/chunking/`

| 전략 | 용도 | 특징 |
|------|------|------|
| default | 일반 텍스트 | 500 토큰 max, 50 토큰 overlap |
| code | 소스 코드 | 코드 블록 보존 |
| tabular | 표 데이터 | 행 단위 처리 |

**DomainAwareChunker**: 파일 확장자/내용 비율로 자동 전략 선택

### 6.3 임베딩

Pinecone Inference API:
- 모델: `multilingual-e5-large`
- 차원: 1024
- 비동기 처리: `asyncio.to_thread()`

### 6.4 벡터 저장소

`backend/src/documents/pinecone_store.py`

```python
# 네임스페이스 격리
namespace = f"user_{user_id}"

# 메타데이터
{
    "document_id": "...",
    "chunk_id": "...",
    "filename": "...",
    "file_type": "...",
    "page": 1,
    "heading": "...",
    "section_type": "paragraph",
    "text": "청크 내용",
    "user_id": "...",
    "session_id": "...",
}
```

---

## 7. 애플리케이션 보안

> **참고**: 인프라 보안(SSL/TLS, DDoS, WAF, CDN Rate Limiting)은 Vercel/Render가 자동 처리

### 7.1 입력 보안

`backend/src/core/prompt_security.py`

**프롬프트 인젝션 탐지** (5개 카테고리):
- JAILBREAK: 시스템 프롬프트 우회 시도
- DATA_EXFILTRATION: 데이터 탈취 시도
- PRIVILEGE_ESCALATION: 권한 상승 시도
- TOOL_MANIPULATION: 도구 조작 시도
- PROMPT_LEAK: 프롬프트 유출 시도

**신뢰도 레벨**: high (차단), medium (경고), low (로그)

### 7.2 출력 보안

`filter_llm_output()`: 프롬프트 유출 패턴 탐지 및 마스킹

### 7.3 인증/인가

- **Supabase JWT**: Bearer 토큰 인증
- **get_current_user()**: FastAPI 의존성
- **API 엔드포인트 권한**: `CurrentUser` 의존성 추가로 제어

### 7.4 파일 업로드 보안

`backend/src/core/validators.py`

- 매직 바이트 검증 (PDF: `%PDF`, DOCX: `PK`)
- MIME 타입 일치 확인
- 파일 크기 제한 (10MB)
- PII 탐지 (이메일, 전화번호, SSN, 신용카드, API 키, IP)

### 7.5 프론트엔드 보안

`frontend/src/lib/security-validator.ts`

- 4단계 심각도: critical, error, warning, info
- XSS 패턴 탐지 (script, event handlers, iframe, object, embed)
- `sanitizeInput()`: null byte, 과도한 반복, 개행 제거

---

## 8. 인프라 & 배포

### 8.1 로컬 개발

`docker-compose.yml`

```yaml
services:
  backend:    FastAPI (port 8000)
  frontend:   Next.js (port 3000)
  redis:      Redis 7 Alpine (port 6379)
  ollama:     Ollama (port 11434)
```

### 8.2 프로덕션

| 서비스 | 플랫폼 | 용도 |
|--------|--------|------|
| 백엔드 | Render | FastAPI 앱 |
| 프론트엔드 | Vercel | Next.js 앱 |
| Vector DB | Pinecone | 관리형 벡터 DB |
| 세션 메모리 | Upstash Redis | 관리형 Redis |
| 인증 | Supabase | Auth + User Management |

### 8.3 CI/CD

`.github/workflows/ci-cd.yml`

```
PR 트리거:
├── ci-backend: ruff lint, pytest (unit)
├── ci-frontend: npm lint, type-check, build
└── ci-security: Trivy scan, npm audit

main 브랜치 push:
├── cd-render: 백엔드 배포
├── cd-vercel: 프론트엔드 배포
└── health-check: 배포 후 헬스 체크 (10회 재시도, 10초 간격)
```

---

## 9. 설계 패턴

### 9.1 Protocol 지향 아키텍처

```python
@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, messages: list[dict], **kwargs) -> str: ...

# 상속 없이 구현 가능
class OpenAIProvider:
    async def generate(self, messages, **kwargs) -> str: ...
```

### 9.2 Factory 패턴

```python
# 데코레이터로 자동 등록
@LLMFactory.register("openai")
class OpenAIProvider: ...

# 설정 기반 인스턴스화
llm = LLMFactory.create(config.llm)
```

### 9.3 Strategy 패턴

```python
# 설정만 변경하면 구현체 교체
memory:
  backend: redis    → RedisStore
  backend: in_memory → InMemoryStore
```

### 9.4 의존성 주입

**dependency-injector** 라이브러리 사용:

```python
@router.post("/chat")
@inject
async def chat(
    request: ChatRequest,
    graph=Depends(Provide[DIContainer.graph]),
) -> ChatResponse:
    ...
```

---

## 핵심 강점

1. **AI 네이티브**: LangGraph 기반 멀티 에이전트 오케스트레이션
2. **타입 안전**: Python 3.12 + TypeScript 전 레이어
3. **확장 가능**: Protocol + Factory로 느슨한 결합
4. **프로덕션 레디**: Docker, 보안, CI/CD 완비
5. **비용 효율**: 무료 티어 기반 (Pinecone, Render, Vercel)

---

*최종 업데이트: 2026-02-17*
