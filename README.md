# AI Agent Chatbot

LangGraph 기반 cost-aware 멀티 에이전트 챗봇 시스템입니다. Heuristic Router가 LLM 호출 없이 작업 큐를 만들고, Web Search/Retriever tool node가 필요한 컨텍스트를 수집한 뒤 Chat/Code/RAG/Report 전문 에이전트가 응답합니다.

## 현재 상태

- 프론트엔드: Next.js 16 + React 19 + Zustand
- 백엔드: FastAPI + LangGraph + dependency-injector
- LLM: OpenRouter (`openrouter/free`, 유료 fallback 없음)
- 세션/메모리: Redis 우선, 로컬에서는 In-Memory fallback
- RAG: Pinecone + 문서 업로드 파이프라인
- 배포: Render(백엔드) + Vercel(프론트엔드)

## 그래프 구조

```
사용자 입력
  → router (LLM 없음, 키워드 기반 task queue)
      → chat
      → code
      → web_search_collect → chat
      → retriever_collect → rag
      → web_search_collect → retriever_collect → report
  → END
```

기본 LLM 호출: 쿼리당 1회. 검색/RAG 수집은 deterministic tool node로 처리합니다.

## 주요 기능

- Heuristic task queue 기반 단일 LLM 호출 챗
- 문서 업로드 후 질의응답 (retriever tool)
- 웹 검색 도구 연동 (Tavily)
- 코드 관련 질의 처리
- 4개 LLM-backed specialist agent: Chat, Code, RAG, Report
- 세션 메모리 저장 및 요약
- SSE 기반 스트리밍 응답
- `/dashboard` 운영 대시보드

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
uv run pytest -v

# frontend
cd frontend
npm run lint
npm run build
```

## 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DEPLOYMENT.md](./DEPLOYMENT.md)
- [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)
