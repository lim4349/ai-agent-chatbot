# AI Agent Chatbot - AGENTS.md

> AI 에이전트 개발을 위한 프로젝트 가이드

---

## 프로젝트 개요

LangGraph 기반 멀티 에이전트 챗봇 시스템. Supervisor가 사용자 질의를 분석하여 RAG, Web Search, Code, Chat 에이전트 중 적절한 것으로 라우팅합니다.

**핵심 특징**:
- 멀티 에이전트 오케스트레이션 (LangGraph)
- RAG 파이프라인 (ChromaDB + OpenAI Embeddings)
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
| **LLM** | OpenAI / Anthropic | GPT-4o / Claude |
| **Vector DB** | ChromaDB | 0.5.x |
| **Session** | Redis | 7.x |
| **배포** | Docker Compose | - |

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
├── docker-compose.yml     # 로컬 개발 환경
├── ARCHITECTURE.md        # 아키텍처 문서
└── README.md              # 프로젝트 소개
```

---

## 개발 가이드

### 1. 로컬 개발 환경 설정

```bash
# 1. 저장소 클론
git clone <repository-url>
cd ai-agent-chatbot

# 2. 환경 변수 설정
cp backend/.env.example backend/.env
# .env 파일에 API 키 설정

# 3. Docker Compose로 실행
docker-compose up -d

# 4. 확인
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 2. 코드 스타일

**Python (Ruff)**:
```bash
cd backend
ruff check src/          # 린트 체크
ruff format src/         # 포맷팅
```

**TypeScript (ESLint/Prettier)**:
```bash
cd frontend
npm run lint             # 린트 체크
npm run format           # 포맷팅
```

### 3. 테스트 실행

```bash
# 백엔드 테스트
cd backend
pytest tests/ -v

# 프론트엔드 테스트
cd frontend
npm test
```

### 4. Git Workflow

```
feature/my-feature → develop → main
```

- `main`: 프로덕션 브랜치
- `develop`: 개발 브랜치
- `feature/*`: 기능 브랜치

---

## 핵심 패턴

### 1. Protocol 지향 설계

```python
# Interface 정의
@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, messages: list[dict], **kwargs) -> str: ...

# 구현 (상속 불필요)
class OpenAIProvider:
    async def generate(self, messages: list[dict], **kwargs) -> str:
        # 구현
```

### 2. DI 컨테이너 패턴

```python
@dataclass
class Container:
    config: AppConfig

    @cached_property
    def llm(self) -> LLMProvider:
        return LLMFactory.create(self.config.llm)

    def override(self, **kwargs) -> "Container":
        # 테스트용 의존성 오버라이드
        ...
```

### 3. Factory 패턴

```python
# 자동 등록
@LLMFactory.register("openai")
class OpenAIProvider: ...

# 사용
llm = LLMFactory.create(config)  # "openai" → OpenAIProvider
```

---

## 에이전트 개발

### 새로운 에이전트 추가

```python
# 1. src/agents/my_agent.py 생성
class MyAgent(BaseAgent):
    def __init__(self, llm: LLMProvider, ...):
        super().__init__(llm=llm)

    async def process(self, state: AgentState) -> AgentState:
        # 에이전트 로직
        response = await self.llm.generate(messages)
        return {
            **state,
            "messages": [...state["messages"], {"role": "assistant", "content": response}],
            "next_agent": END  # 또는 다음 에이전트
        }

# 2. AgentFactory에 등록
class AgentFactory:
    @staticmethod
    def create_my_agent(container: Container) -> MyAgent:
        return MyAgent(llm=container.llm, ...)

# 3. graph/builder.py에 추가
my_agent = AgentFactory.create_my_agent(container)
graph.add_node("my_agent", my_agent)
```

---

## API 개발

### 새로운 엔드포인트

```python
# src/api/routes.py
@router.post("/my-endpoint", response_model=MyResponse)
async def my_endpoint(
    request: MyRequest,
    container: Container = Depends(get_container_dependency),
) -> MyResponse:
    # 1. 입력 검증 (Pydantic이 자동 수행)
    # 2. 비즈니스 로직
    result = await container.my_service.process(request.data)
    # 3. 응답
    return MyResponse(result=result)
```

---

## 배포

### 묣가 티어 (추천)

| 서비스 | 용도 | 제공량 |
|--------|------|--------|
| Render.com | 백엔드 | 512MB RAM |
| Vercel | 프론트엔드 | 100GB/월 |
| GitHub Actions | CI/CD | 무제한 (Public) |

### 배포 명령어

```bash
# GitHub Actions가 자동 배포
# main 브랜치 푸시 시:
# 1. 테스트 실행
# 2. Docker 이미지 빌드
# 3. Render.com & Vercel 배포
```

---

## 문제 해결

### 일반적인 문제

**ChromaDB 연결 실패**:
```bash
# ChromaDB 컨테이너 확인
docker-compose ps chromadb
# 로그 확인
docker-compose logs chromadb
```

**Redis 연결 실패**:
```bash
docker-compose ps redis
docker-compose logs redis
```

**Python 의존성 충돌**:
```bash
cd backend
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

---

## 참고 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 상세 아키텍처
- [backend/AGENTS.md](./backend/AGENTS.md) - 백엔드 개발 가이드
- [frontend/AGENTS.md](./frontend/AGENTS.md) - 프론트엔드 개발 가이드
- [README.md](./README.md) - 프로젝트 소개

---

## 팀 연락처

- **개발자**: [Your Name]
- **이메일**: [your.email@example.com]
- **프로젝트**: AI Agent Chatbot
- **라이선스**: MIT

---

*마지막 업데이트: 2026-02-15*
