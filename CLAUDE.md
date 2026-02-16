# AI Agent Chatbot - Project Context

> LangGraph 기반 멀티 에이전트 챗봇 시스템

---

## 프로젝트 개요

Supervisor가 사용자 질의를 분석하여 RAG, Web Search, Code, Chat 에이전트 중 적절한 것으로 라우팅합니다.

**핵심 특징**:
- 멀티 에이전트 오케스트레이션 (LangGraph)
- RAG 파이프라인 (Pinecone + Pinecone Inference Embeddings)
- 실시간 스트리밍 응답 (SSE)
- 구조 기반 문서 청킹
- 메모리 관리 (Redis + 요약)

---

## 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| **프론트엔드** | Next.js + TypeScript | 16.x |
| **백엔드** | FastAPI + Python | 3.12 |
| **AI** | LangGraph + LangChain | 0.2.x |
| **LLM** | OpenAI / Anthropic / GLM | GPT-4o / Claude / GLM-4 |
| **Vector DB** | Pinecone | - |
| **Embedding** | Pinecone Inference (multilingual-e5-large) | - |
| **Session** | Redis | 7.x |
| **배포** | Render + Vercel | - |

---

## 프로젝트 구조

```
.
├── frontend/              # Next.js 16 프론트엔드
│   ├── src/
│   │   ├── app/          # App Router
│   │   ├── components/   # React 컴포넌트
│   │   ├── lib/          # 유틸리티
│   │   └── stores/       # Zustand 상태관리
│   └── package.json
│
├── backend/               # FastAPI 백엔드
│   ├── src/
│   │   ├── agents/       # 에이전트 구현
│   │   ├── api/          # REST API
│   │   ├── core/         # DI 컨테이너, 설정
│   │   ├── documents/    # 문서 처리 (파서, 청커)
│   │   ├── graph/        # LangGraph 상태 머신
│   │   ├── llm/          # LLM 프로바이더
│   │   ├── memory/       # 메모리 저장소
│   │   └── tools/        # 도구 (MCP, 웹 검색 등)
│   ├── tests/
│   └── pyproject.toml
│
├── .github/workflows/     # CI/CD
├── docker-compose.yml     # 로컬 개발 환경
├── ARCHITECTURE.md        # 아키텍처 문서
└── README.md              # 프로젝트 소개
```

---

## 개발 가이드

### 1. 로컬 개발 환경 설정

```bash
# 1. 환경 변수 설정
cp backend/.env.example backend/.env

# 2. 가상환경 생성 및 활성화 (필수!)
cd backend
python -m venv .venv
source .venv/bin/activate

# 3. 의존성 설치
pip install -e ".[dev]"

# 4. 프론트엔드
cd ../frontend
npm install

# 5. 확인
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

### 2. 코드 스타일

**Python (Ruff)**:
```bash
cd backend
source .venv/bin/activate  # 가상환경 필수!
ruff check src/            # 린트 체크
ruff format src/           # 포맷팅
```

**TypeScript (ESLint)**:
```bash
cd frontend
npm run lint               # 린트 체크
npm run build              # 빌드 테스트
```

### 3. 테스트 실행

```bash
# 백엔드 테스트 (가상환경에서)
cd backend
source .venv/bin/activate
pytest tests/ -v

# 프론트엔드 테스트
cd frontend
npm test
```

### 4. Git Workflow

```
feature/* → dev → main
```

- `main`: 프로덕션 브랜치 (자동 배포)
- `dev`: 개발 브랜치
- `feature/*`: 기능 브랜치

---

## 핵심 패턴

### 1. Protocol 지향 설계

```python
@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, messages: list[dict], **kwargs) -> str: ...
```

### 2. DI 컨테이너 패턴

```python
@dataclass
class Container:
    config: AppConfig

    @cached_property
    def llm(self) -> LLMProvider:
        return LLMFactory.create(self.config.llm)
```

### 3. Factory 패턴

```python
@LLMFactory.register("openai")
class OpenAIProvider: ...

llm = LLMFactory.create(config)  # 자동 매핑
```

---

## 배포

### 무료 티어

| 서비스 | 용도 | 비고 |
|--------|------|------|
| Render.com | 백엔드 | 512MB RAM, Public repo = 무제한 CI |
| Vercel | 프론트엔드 | 100GB/월 |
| Pinecone | Vector DB | 무료 tier |
| GitHub Actions | CI/CD | Public repo 무제한 |

### 배포 프로세스

1. `dev` 브랜치에서 개발
2. PR 생성 → CI 테스트
3. `main` 머지 → 자동 배포

---

## 참고 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 상세 아키텍처
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 배포 가이드
- [backend/AGENTS.md](./backend/AGENTS.md) - 백엔드 상세 가이드
- [frontend/AGENTS.md](./frontend/AGENTS.md) - 프론트엔드 상세 가이드

---

*마지막 업데이트: 2026-02-16*
