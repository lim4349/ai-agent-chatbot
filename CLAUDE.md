# AI Agent Chatbot - 개발 가이드

## 개요

LangGraph 기반 챗봇입니다. FastAPI 백엔드와 Next.js 프론트엔드가 분리되어 있습니다.

**그래프 구조**: `heuristic_router(LLM 없음)` → `[chat | code | report]` → END
- LLM 호출: 쿼리당 최소 1회 (기존 supervisor 방식은 2회+)
- `chat` 에이전트가 web_search/retriever 툴을 직접 pre-fetch해서 단일 LLM 호출로 처리
- `code`, `report`는 전용 에이전트 유지

## 현재 기술 스택

- Backend: Python 3.12, FastAPI, LangGraph, dependency-injector
- Frontend: Next.js 16, React 19, TypeScript, Zustand
- LLM: OpenRouter/OpenAI-compatible provider 중심
- Memory: Redis 우선, 로컬/장애 시 In-Memory fallback
- RAG: Pinecone + 문서 파서(pdf/docx/txt/md/csv/json)
- Observability: structlog, LangSmith optional

## 실행

```bash
# backend
cd backend
uv sync --group dev
uv run uvicorn src.main:app --reload

# frontend
cd ../frontend
npm install
npm run dev
```

## 테스트와 검증

```bash
# backend
cd backend
uv run pytest -v
uv run ruff check src tests

# frontend
cd frontend
npm run lint
npm run build
```

## 코드 구조 원칙

- API 진입점은 `backend/src/main.py`
- 라우트는 `backend/src/api`
- 에이전트 구현은 `backend/src/agents`
- 상태 그래프는 `backend/src/graph`
- 메모리/세션은 `backend/src/memory`
- 프론트 라우트는 `frontend/src/app`

## 작업 시 유의사항

- 설정은 `.env`와 `src/core/config` 계층을 우선 확인
- 새 기능은 DI 컨테이너와 기존 service/tool registry 구조를 따라야 함
- Redis가 없어도 동작하는 fallback 경로를 깨지 않도록 주의
- 프론트는 `/chat`, `/dashboard`의 사용자 플로우를 우선 검증
- LLM 모델: `openrouter/free` (OpenRouter free router, 유료 fallback 없음)
- 라우팅 수정은 `src/graph/router.py`의 regex 패턴 조정
- chat agent의 tool pre-fetch 로직은 `src/agents/chat_agent.py` `process()` 내 tools_hint 처리 부분

## 커밋 전 최소 확인

```bash
cd backend && uv run pytest -v
cd frontend && npm run lint && npm run build
```
