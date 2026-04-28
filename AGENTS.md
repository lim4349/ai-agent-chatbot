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

- Keep `TOOLS_CODE_EXECUTION_ENABLED=false` by default.
- Render Free Tier should not enable code execution.
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
