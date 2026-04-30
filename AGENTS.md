# AGENTS.md

Project-wide guidance for AI coding agents working in this repository.

## Project Overview

- Frontend: Next.js 16, React 19, Zustand, shadcn/ui-style components
- Backend: FastAPI, LangGraph, dependency-injector
- LLM provider: OpenRouter via OpenAI-compatible API
- Production model: `openrouter/free`
- Vector/RAG: Pinecone
- Short-term memory: Redis/Upstash in production, in-memory fallback locally
- Deployment: Render backend, Vercel frontend

## Current Agent Architecture

Active LangGraph flow:

```text
FastAPI
→ LangGraph
   → LLMRouterNode
      ├─ ChatAgent
      └─ ResearchAgent
            ├─ web_search
            └─ retriever
```

- Active agents: `chat`, `research`
- Active tools: `web_search`, `retriever`
- `ResearchAgent` decides when to call tools. Explicit RAG/document questions must use `retriever`; current/news/search questions use `web_search`.
- Do not reintroduce separate `code`, `rag`, `report`, collect-node, MCP, or code-execution surfaces unless the user explicitly requests a new architecture.

## Current LLM Policy

Use OpenRouter's free router as the single production model.

Required backend environment:

```env
LLM_PROVIDER=openai
LLM_MODEL=openrouter/free
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_OPENAI_API_KEY=sk-or-v1-...
```

Do not add hardcoded free-model fallback chains in application code. `openrouter/free`
already routes to available free models. Keep the OpenRouter `max_price` guard at zero
so paid routing is not used accidentally.

## Security Defaults

- Keep the active tool surface limited to `web_search` and `retriever`.
- Log endpoints are debug-only. Do not expose `/api/v1/logs` in production.
- Do not commit real secrets. Use `.env.example` placeholders and configure secrets in
  Render, Vercel, or GitHub Actions.

## Backend Workflow

Run backend commands from `backend/`.

```bash
uv run --with ruff ruff check .
uv run --with pytest --with pytest-asyncio --with pytest-cov --with pytest-timeout python -m pytest -q
```

Important patterns:

- Use the existing `DIContainer` providers and `@inject`/`Provide[...]` route pattern.
- Factory functions in `src/core/di_container.py` should stay above the container class.
- Prefer Protocol-compatible implementations over inheritance-heavy abstractions.
- For blocking third-party SDK calls inside async flows, use `asyncio.to_thread`.

## Frontend Workflow

Run frontend commands from `frontend/`.

```bash
npm run lint
npm test
npm run build
```

Frontend rules:

- Keep UI changes consistent with existing Tailwind/shadcn-style components.
- Avoid adding broad UI rewrites while fixing narrow bugs.
- Keep Zustand store changes scoped and preserve persisted state shape unless migration is intentional.

## CI/CD Notes

- Pull requests run CI checks.
- Pushes to `main` trigger production deployment through GitHub Actions.
- Required GitHub Secrets for deployment:

```env
RENDER_API_KEY=...
RENDER_BACKEND_SERVICE_ID=...
RENDER_URL=https://your-render-backend.onrender.com
VERCEL_TOKEN=...
VERCEL_ORG_ID=...
VERCEL_PROJECT_ID=...
```

Optional:

```env
RENDER_REDIS_SERVICE_ID=...
```

## Change Discipline

- Keep edits surgical and tied to the user's request.
- Do not reformat or refactor unrelated code.
- Do not revert user changes unless explicitly asked.
- If tests are changed, make sure the relevant test command actually runs in CI.
- Before finalizing, report which checks were run and whether anything remains unverified.


<claude-mem-context>
# Memory Context

# [ai-agent-chatbot] recent context, 2026-04-28 12:54pm GMT+9

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (16,800t read) | 180,666t work | 91% savings

### Mar 7, 2026
2121 4:38p 🔵 CI/CD Pipeline Failure on Main Branch
2122 " 🔵 Production Deployment Health Check Failure
S237 CI/CD health check timeout fixes for Render deployment (Mar 7, 4:43 PM)
2124 4:43p 🔵 GitHub workflow files found in parent directory
2125 " 🔵 CI/CD workflow health check mechanism examined
2126 4:44p 🔴 Health check timing fixed with initial delay and increased retries
2127 " ✅ Health check fix committed and pushed to dev branch
2128 " ✅ PR #185 created for health check timing fix
2129 " ✅ PR #185 merged into main branch
2130 " ✅ PR #185 merge confirmed successful
S238 Docker build and server restart test (requested in Korean) (Mar 7, 7:33 PM)
S239 PydanticAI migration analysis compared to current LangGraph architecture (Mar 7, 7:33 PM)
### Mar 8, 2026
2131 10:24p 🔵 Claude SDK and ADK comparison request
S240 LangGraph vs PydanticAI vs Google ADK comparison for multi-agent framework evaluation (Mar 8, 10:24 PM)
S241 Whisper STT and TTS service options research and recommendations for agentic RAG project (Mar 8, 10:35 PM)
### Mar 11, 2026
2133 9:49a 🔵 Researching free web-based Whisper and TTS services
2134 9:50a 🔵 Web search for free Whisper and TTS API services failed
S242 Analysis of current RAG implementation and comparison with Agentic RAG architecture (Mar 11, 9:52 AM)
2135 9:53a 🔵 Agentic RAG Architecture Considerations for Portfolio Project
S243 LlamaIndex purpose inquiry and framework comparison for Agentic RAG implementation (Mar 11, 9:55 AM)
S244 Planning Agentic RAG implementation after deleting previous work direction (Mar 11, 9:55 AM)
2136 9:55a 🟣 New Agentic RAG project repository initialized
2137 " ✅ Project documentation and configuration files created
2138 9:56a 🟣 Python project structure and dependencies configured
2139 " 🟣 Configuration management and embedding system implemented
2140 " 🟣 ChromaDB vector store wrapper implemented
2141 9:57a 🟣 Agentic RAG system with self-reflection and multi-hop reasoning implemented
2142 " ✅ Agentic RAG project directory deleted
2143 " 🔵 Investigation into GLM ZAI coding plan performance issues
S245 PostgreSQL 통합 아키텍처로 Agentic RAG 구현 방안 논의 (Mar 11, 9:58 AM)
2144 9:58a 🔵 User investigating GLM ZAI coding plan performance issues
2145 10:00a 🟣 Created new Agentic RAG project directory with Pydantic
2146 " 🟣 Established full-stack project structure for Agentic RAG application
2147 10:01a 🟣 Expanded project structure with API layer and testing directory
2148 " 🟣 Initialized Agentic RAG project with FastAPI, Pydantic AI, and Supabase
2149 " 🟣 Implemented Pydantic Settings configuration system for backend
2150 " 🟣 Implemented Supabase pgvector store with OpenAI embeddings
2151 10:02a ✅ Deleted Agentic RAG project directory completely
S246 RAG 시스템 요구사항 정의 및 기술 스택 확정 (Mar 11, 10:02 AM)
2152 10:17a 🔵 GLM Zai Coding Plan Performance Investigation Request
### Apr 28, 2026
4678 10:52a 🔵 Codex skill-installer requires explicit skill name, rejects root path
4679 10:53a 🔵 karpathy-codex-skills repository provides three packaging styles
4680 " 🟣 Installed 5 Karpathy coding guideline skills to Codex
4681 10:54a 🔵 Multi-agent chatbot architecture with supervisor routing and RAG
4682 " 🔵 Test infrastructure and code quality baseline assessment
4683 10:55a 🔵 Production deployment architecture and infrastructure patterns
4684 10:56a 🔴 Backend pytest infrastructure fixed via uv --with pattern
4685 10:59a 🔴 Fixed Ruff lint violation and hardened CI test reliability
4686 " 🔴 Fixed frontend test failures and added missing test script
4687 11:00a 🔴 All frontend tests now passing after test infrastructure fixes
4688 " 🟣 Production security hardening for debug log endpoints
4689 11:23a 🔵 OpenRouter free model endpoint validated
4690 11:25a 🔵 Free-model-only LLM configuration with enforced cost protection
4691 " 🔵 Multi-provider free-tier fallback chain mitigates rate limits
4692 11:26a 🔄 Simplified LLM configuration to use openrouter/free alias exclusively
4693 11:27a ✅ Refactor validated with full test suite and production build
4694 " 🔵 Git ignore rule blocks staging frontend/src/lib directory
4695 11:28a ✅ Committed openrouter/free refactor to version control
4696 " 🟣 Added root AGENTS.md with project-wide AI agent guidance
4697 " ✅ Deployed openrouter/free refactor to production

Access 181k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>
