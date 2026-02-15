# AI Agent Chatbot

LangGraph 기반 Multi-Agent 챗봇 시스템. Supervisor 패턴으로 4개 전문 에이전트를 오케스트레이션하며, Protocol 기반 의존성 주입과 확장 가능한 아키텍처를 적용한 프로젝트.

## 빠른 시작

### 1. 백엔드 설정

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
# .env 파일에 API 키 설정 (OPENAI_API_KEY 또는 ANTHROPIC_API_KEY)
```

### 2. 프론트엔드 설정

```bash
cd frontend
npm install

cp .env.example .env.local
# NEXT_PUBLIC_API_URL 기본값: http://localhost:8000
```

### 3. 개발 서버 실행

```bash
# 백엔드 (8000번 포트)
cd backend
uvicorn src.main:app --reload

# 프론트엔드 (3000번 포트)
cd frontend
npm run dev

# 또는 Docker로 전체 실행
docker compose up -d
```

### 4. 접속

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API 문서: http://localhost:8000/docs

## 환경 변수 설정

`backend/.env`:

```bash
# OpenAI 사용 시
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_OPENAI_API_KEY=sk-...

# Anthropic 사용 시
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
LLM_ANTHROPIC_API_KEY=sk-ant-...

# 또는 GLM (z.ai)
LLM_PROVIDER=anthropic
LLM_MODEL=glm-4.7
LLM_ANTHROPIC_API_KEY=your-key
LLM_BASE_URL=https://api.z.ai/api/anthropic
```

## 개발 명령어

```bash
# 백엔드
cd backend
uvicorn src.main:app --reload        # 개발 서버
pytest tests/ -v                      # 테스트
ruff check src/ tests/                # 린트
ruff format src/ tests/               # 포맷팅

# 프론트엔드
cd frontend
npm run dev                           # 개발 서버
npm run build                         # 빌드
npm run lint                          # 린트

# Docker
docker compose up -d                  # 전체 서비스 시작
docker compose down                   # 중지
docker compose logs -f                # 로그
```

## 기술 스택

**Backend**: Python 3.12, FastAPI, LangGraph, LangChain, dependency-injector, ChromaDB, Redis

**Frontend**: Next.js 16, TypeScript, Tailwind CSS 4, Zustand, shadcn/ui

**Infrastructure**: Docker, Render.com, Vercel

## 프로젝트 구조

```
ai-agent-chatbot/
├── backend/           # FastAPI + LangGraph
│   ├── src/           # 소스 코드
│   ├── tests/         # 테스트
│   └── Dockerfile
├── frontend/          # Next.js
│   ├── src/           # 소스 코드
│   └── Dockerfile
├── docker-compose.yml # 로컬 개발 환경
└── README.md
```

## 문서

- [아키텍처 문서](./ARCHITECTURE.md) — 시스템 설계 및 아키텍처
- [배포 가이드](./DEPLOYMENT.md) — Render.com + Vercel 배포 방법
- [백엔드 가이드](./backend/AGENTS.md) — 백엔드 개발 가이드
- [프론트엔드 가이드](./frontend/AGENTS.md) — 프론트엔드 개발 가이드
- [학습 사항](./LESSONS.md) — PR 리뷰에서 발견된 문제와 해결책 (자동 업데이트)

## 라이선스

MIT
