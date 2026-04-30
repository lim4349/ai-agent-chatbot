# AI Agent Chatbot

LangGraph 기반 멀티 에이전트 챗봇 시스템입니다. LLM Router가 `chat` 또는 `research` 전문 에이전트를 선택하고, `research` 에이전트가 필요할 때 `web_search`와 `retriever` 도구를 agentic tool calling 방식으로 선택해 사용합니다.

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
  → router (LLM 기반 agent routing)
      → chat
      → research
          ├─ web_search
          └─ retriever
  → END
```

기본 LLM 호출:

- 일반 대화: 라우팅 1회 + ChatAgent 응답 1회
- 리서치/RAG/보고서: 라우팅 1회 + ResearchAgent 도구 선택 1회 + 최종 응답 1회

## 주요 기능

- LLM 기반 멀티 에이전트 라우팅
- 2개 LLM-backed specialist agent: Chat, Research
- ResearchAgent 내부 agentic tool calling
- 문서 업로드 후 질의응답 (`retriever`)
- 웹 검색 도구 연동 (`web_search`, Tavily)
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
