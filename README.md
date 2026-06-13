# AI Agent Chatbot

LangGraph 기반 Agentic RAG 챗봇 시스템입니다. 단일 `assistant` 에이전트가 대화와 메모리를 처리하고, 필요할 때 `web_search`와 `retriever` 도구로 Research Evidence를 수집해 답변합니다.

## 현재 상태

- 프론트엔드: Next.js 16 + React 19 + Zustand
- 백엔드: FastAPI + LangGraph + dependency-injector
- LLM: OpenRouter (`openrouter/free`, 유료 fallback 없음)
- 세션/메모리: Redis 우선, 로컬에서는 In-Memory fallback
- RAG: Pinecone + layout-aware 문서 업로드 파이프라인
- 배포: Render(백엔드) + Vercel(프론트엔드)

## 그래프 구조

```
사용자 입력
  → assistant
      ├─ conversation memory
      ├─ web_search
      └─ retriever
  → END
```

기본 LLM 호출:

- 일반 대화: AssistantAgent 응답 1회
- 리서치/RAG/보고서: AssistantAgent 도구 선택 1회 + 필요한 도구 호출 + 최종 응답 1회

## 주요 기능

- 단일 AssistantAgent 기반 Agentic RAG 흐름
- Research Evidence 기반 agentic tool calling
- 문서 업로드, layout-aware parsing, parent-child retrieval, 목록/삭제 후 질의응답 (`retriever`)
- 웹 검색 도구 연동 (`web_search`, Tavily)
- 세션 메모리 저장 및 요약
- SSE 기반 스트리밍 응답
- `/dashboard` 운영 대시보드
- CI에서 실행 가능한 offline RAG evaluation JSONL gate

## 디렉토리 구조

```text
ai-agent-chatbot/
├── backend/
│   ├── src/
│   │   ├── agents/
│   │   ├── api/
│   │   ├── core/
│   │   ├── documents/
│   │   ├── graph/
│   │   ├── llm/
│   │   ├── memory/
│   │   ├── observability/
│   │   └── tools/
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/
│       ├── components/
│       ├── lib/
│       └── stores/
├── nginx/
├── ARCHITECTURE.md
├── DEPLOYMENT.md
├── PROJECT_SUMMARY.md
└── docker-compose.yml
```

## 로컬 실행

### Backend

```bash
cd backend
uv sync --group dev
uv run uvicorn src.main:app --reload
```

기본 API:

- `GET /`
- `GET /docs`
- `GET /api/v1/health`
- `POST /api/v1/chat`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

기본 페이지:

- `/`
- `/chat`
- `/dashboard`

### Docker Compose

```bash
docker compose up -d --build
```

기본 포트:

- frontend: `3000`
- backend: `8000`
- nginx: `80`
- redis: `6379`

## 개발 체크

```bash
# backend
cd backend
uv run --with ruff ruff check .
uv run --with pytest --with pytest-asyncio --with pytest-cov --with pytest-timeout python -m pytest -q
uv run python -m src.evaluation.rag_eval evals/research_golden.jsonl --min-source-hit-rate 1.0 --min-answer-coverage-rate 1.0 --max-no-answer-rate 0.0 --min-tool-match-rate 1.0 --min-confidence-pass-rate 1.0 --min-citation-page-hit-rate 1.0 --min-heading-path-hit-rate 1.0 --min-table-answer-coverage-rate 1.0 --min-parent-hydration-rate 1.0

# frontend
cd frontend
npm run lint
npm test
npm run build
```

## 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DEPLOYMENT.md](./DEPLOYMENT.md)
- [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)
