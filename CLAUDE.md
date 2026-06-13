# AI Agent Chatbot - 개발 가이드

## 개요

LangGraph 기반 챗봇입니다. FastAPI 백엔드와 Next.js 프론트엔드가 분리되어 있습니다.

**그래프 구조**: `assistant` → END
- 일반 대화: AssistantAgent 최종 응답 1회
- 리서치/RAG/보고서: ResearchEvidenceCollector 도구 선택 1회 + 필요한 도구 호출 + AssistantAgent 최종 응답 1회
- `assistant` 에이전트가 대화/메모리를 담당하고, `ResearchEvidenceCollector`가 `web_search`/`retriever` 사용 여부를 결정

## 현재 기술 스택

- Backend: Python 3.12, FastAPI, LangGraph, dependency-injector
- Frontend: Next.js 16, React 19, TypeScript, Zustand
- LLM: OpenRouter/OpenAI-compatible provider 중심
- Memory: Redis 우선, 로컬/장애 시 In-Memory fallback
- RAG: Pinecone + layout-aware 문서 파서(pdf/docx/txt/md/csv/json) + parent-child retrieval
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
uv run --with ruff ruff check .
uv run --with pytest --with pytest-asyncio --with pytest-cov --with pytest-timeout python -m pytest -q
uv run python -m src.evaluation.rag_eval evals/research_golden.jsonl \
  --min-source-hit-rate 1.0 \
  --min-answer-coverage-rate 1.0 \
  --max-no-answer-rate 0.0 \
  --min-tool-match-rate 1.0 \
  --min-confidence-pass-rate 1.0 \
  --min-citation-page-hit-rate 1.0 \
  --min-heading-path-hit-rate 1.0 \
  --min-table-answer-coverage-rate 1.0 \
  --min-parent-hydration-rate 1.0

# frontend
cd frontend
npm run lint
npm test
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
- 새 기능은 DI 컨테이너와 기존 agent/tool registry 구조를 따라야 함
- Redis가 없어도 동작하는 fallback 경로를 깨지 않도록 주의
- 프론트는 `/chat`, `/dashboard`의 사용자 플로우를 우선 검증
- LLM 모델: `openrouter/free` (OpenRouter free router, 유료 fallback 없음)
- 문서 업로드는 `POST /api/v1/documents/upload` 경로만 사용하며 `device_id`와 `session_id`로 격리
- 문서 파싱은 heading path, page/table metadata, parse warning을 보존하고 parent-child retrieval record로 Pinecone에 저장
- 프론트는 guest-first이며 로그인 화면, auth provider, route guard를 다시 추가하지 않음
- 세션 삭제는 session memory, topic summaries, RAG documents, session row만 삭제하고 user facts/profile은 `/api/v1/users/{user_id}/memory`에서만 삭제
- 대화/메모리 흐름 수정은 `src/agents/assistant_agent.py` 조정
- 도구 선택 수정은 `src/agents/research_evidence.py`의 `ResearchToolDecision` 및 guardrail 로직 조정

## 커밋 전 최소 확인

```bash
cd backend && uv run --with ruff ruff check .
cd backend && uv run --with pytest --with pytest-asyncio --with pytest-cov --with pytest-timeout python -m pytest -q
cd frontend && npm run lint && npm test && npm run build
```
