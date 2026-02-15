# Backend AGENTS.md

> FastAPI + Python 3.12 AI Chatbot 백엔드 개발 가이드

---

## 개요

FastAPI 기반의 AI 챗봇 백엔드. LangGraph 멀티 에이전트 아키텍처와 Protocol 기반 DI를 적용한 프로덕션 수준 API 서버입니다.

---

## 기술 스택

| 구성 요소 | 기술 | 버전 | 용도 |
|-----------|------|------|------|
| **Framework** | FastAPI | 0.115+ | 고성능 ASGI API 서버 |
| **Language** | Python | 3.12+ | 타입 힌트, 최신 문법 |
| **AI/LLM** | LangGraph | 0.2+ | 멀티 에이전트 오케스트레이션 |
| **LLM Integration** | LangChain | 0.3+ | OpenAI/Anthropic/Ollama 통합 |
| **Validation** | Pydantic | 2.0+ | 데이터 검증 및 설정 관리 |
| **Vector DB** | ChromaDB | 0.5+ | RAG 및 장기 메모리 저장소 |
| **Session Store** | Redis | 5.0+ | 분산 세션 메모리 (선택) |
| **Logging** | structlog | 24.0+ | 구조화된 JSON 로깅 |
| **Testing** | pytest | 8.0+ | 비동기 테스트 지원 |
| **Linting** | ruff | 0.7+ | 고성능 Python 린터 |

---

## 프로젝트 구조

\`\`\`
backend/
├── src/
│   ├── agents/              # 에이전트 구현
│   │   ├── base.py          # BaseAgent 추상 클래스
│   │   ├── supervisor.py    # SupervisorAgent (라우터)
│   │   ├── chat_agent.py    # ChatAgent (일반 대화)
│   │   ├── code_agent.py    # CodeAgent (코드 생성/분석)
│   │   ├── rag_agent.py     # RAGAgent (문서 기반 Q&A)
│   │   ├── web_search_agent.py  # WebSearchAgent (실시간 검색)
│   │   └── factory.py       # AgentFactory (DI 팩토리)
│   │
│   ├── api/                 # REST API 계층
│   │   ├── routes.py        # API 엔드포인트 정의
│   │   ├── schemas.py       # Pydantic 요청/응답 모델
│   │   ├── dependencies.py  # FastAPI 의존성 주입
│   │   └── middleware.py    # CORS, 로깅, 보안 미들웨어
│   │
│   ├── core/                # 핵심 인프라
│   │   ├── config.py        # Pydantic-settings 기반 설정
│   │   ├── container.py     # DI 컨테이너 (@cached_property)
│   │   ├── protocols.py     # Protocol 기반 인터페이스
│   │   ├── logging.py       # structlog 설정
│   │   ├── auto_summarize.py    # SummarizationManager
│   │   ├── user_profiler.py     # UserProfiler
│   │   └── topic_memory.py      # TopicMemory
│   │
│   ├── documents/           # 문서 처리 (RAG)
│   │   ├── parser.py        # PDF/DOCX/TXT 파싱
│   │   ├── chunker.py       # 구조 인식 청킹
│   │   ├── embeddings.py    # OpenAI 임베딩 생성
│   │   ├── store.py         # ChromaDB 벡터 저장소
│   │   ├── retriever_impl.py    # DocumentRetriever 구현
│   │   └── factory.py       # DocumentProcessorFactory
│   │
│   ├── graph/               # LangGraph 오케스트레이션
│   │   ├── builder.py       # StateGraph 빌더
│   │   ├── state.py         # AgentState 타입 정의
│   │   └── edges.py         # 조건 라우팅 로직
│   │
│   ├── llm/                 # LLM 추상화
│   │   ├── base.py          # LLMProvider Protocol
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── ollama_provider.py
│   │   └── factory.py       # LLMFactory (레지스트리 패턴)
│   │
│   ├── memory/              # 메모리 관리
│   │   ├── base.py          # MemoryStore Protocol
│   │   ├── in_memory_store.py
│   │   ├── redis_store.py
│   │   ├── long_term_memory.py  # ChromaDB 기반 장기 메모리
│   │   └── factory.py       # MemoryStoreFactory
│   │
│   ├── tools/               # 에이전트 도구
│   │   ├── registry.py      # ToolRegistry
│   │   ├── web_search.py    # Tavily 웹 검색
│   │   ├── code_executor.py # RestrictedPython 샌드박스
│   │   ├── retriever.py     # 문서 검색 도구
│   │   └── memory_tool.py   # 시맨틱 메모리 검색
│   │
│   ├── utils/               # 유틸리티
│   │   └── token_counter.py # tiktoken 기반 토큰 계산
│   │
│   └── main.py              # FastAPI 앱 진입점
│
├── tests/                   # 테스트
│   ├── unit/                # 단위 테스트
│   ├── integration/         # 통합 테스트
│   └── conftest.py          # pytest 픽스처
│
├── pyproject.toml           # 프로젝트 설정 (의존성, 도구)
├── Dockerfile               # 컨테이너 이미지
└── .env.example             # 환경 변수 예시
\`\`\`

---

## 개발 가이드

### 1. 환경 설정

\`\`\`bash
# Python 3.12+ 확인
python --version  # Python 3.12.x

# 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

# 의존성 설치 (개발용)
pip install -e ".[dev]"

# 환경 변수 설정
cp .env.example .env
# .env 파일에 API 키 설정 (OPENAI_API_KEY 등)
\`\`\`

### 2. 개발 서버 실행

\`\`\`bash
# 개발 모드 (auto-reload)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 모드
uvicorn src.main:app --host 0.0.0.0 --port 8000
\`\`\`

### 3. 코드 품질

\`\`\`bash
# 린트 검사
ruff check src/

# 린트 자동 수정
ruff check src/ --fix

# 코드 포맷팅
ruff format src/

# 타입 체크
mypy src/ --ignore-missing-imports
\`\`\`

### 4. 테스트 실행

\`\`\`bash
# 전체 테스트
pytest tests/ -v

# 특정 테스트
pytest tests/unit/test_agents.py -v

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html
\`\`\`

---

## 핵심 패턴

### 1. Protocol 기반 설계

\`\`\`python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, messages: list[dict[str, str]], **kwargs) -> str: ...

# 상속 없이 구현 가능
class OpenAIProvider:
    async def generate(self, messages, **kwargs) -> str:
        return response
\`\`\`

### 2. Dependency Injector 기반 DI

**의존성 주입 라이브러리**: `dependency-injector` (DeclarativeContainer)

```python
from dependency_injector import containers, providers
from dependency_injector.wiring import inject, Provide

class DIContainer(containers.DeclarativeContainer):
    """Main dependency injection container."""

    config = providers.Singleton(get_config)
    llm = providers.Factory(_create_llm, config=config.provided.llm)
    memory = providers.Factory(_create_memory, config=config.provided.memory)
    # ... other providers


# @inject 데코레이터 사용 예시
@inject
def my_function(
    llm: LLMProvider = Provide[DIContainer.llm],
    memory: MemoryStore = Provide[DIContainer.memory],
):
    pass
```

#### @inject 데코레이터 패턴

**FastAPI Routes**:
```python
from dependency_injector.wiring import inject, Provide
from src.core.di_container import DIContainer

@router.post("/chat")
@inject
async def chat(
    request: ChatRequest,
    graph: CompiledGraph = Depends(Provide[DIContainer.graph]),
    memory: MemoryStore = Depends(Provide[DIContainer.memory]),
):
    # 의존성이 자동으로 주입됨
    pass
```

**Agent 클래스**:
```python
class SupervisorAgent:
    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        memory: MemoryStore = Provide[DIContainer.memory],
        memory_tool: MemoryTool = Provide[DIContainer.memory_tool],
    ):
        self.llm = llm
        self.memory = memory
        self.memory_tool = memory_tool
```

#### 테스트에서 의존성 오버라이드

```python
import pytest
from src.core.di_container import di_container

@pytest.fixture
def test_container(mock_llm, mock_memory):
    """Create test container with mocked dependencies."""
    # Override providers for testing
    di_container.llm.override(providers.Object(mock_llm))
    di_container.memory.override(providers.Object(mock_memory))

    yield di_container

    # Reset overrides after test
    di_container.reset_singletons()
```

---

## 배포

### Docker 이미지 빌드

\`\`\`bash
docker build -t ai-agent-backend .
docker run -p 8000:8000 --env-file .env ai-agent-backend
\`\`\`

### Render.com 배포

\`\`\`bash
# render.yaml 참고
# GitHub Actions 자동 배포: .github/workflows/ci-cd.yml
\`\`\`

---

## 프로젝트 룰 (Project Rules)

> PR 리뷰에서 발견된 반복적인 패턴과 규칙을 기록합니다.
> 새로운 규칙은 이 섹션에 추가하세요.

### CI/CD

#### Git Flow 브랜칭
- **룰**: 모든 기능 개발은 `feat/*` 브랜치에서 시작하여 `dev`로 PR
- **이유**: `main`은 프로덕션 배포용으로만 사용, 직접 push 금지
- **적용**: `feat/xxx` → `dev` (CI) → `main` (CI+CD)

#### YAML 문법
- **룰**: 같은 키는 한 번만 정의, 브랜치 목록은 배열로 관리
- **이유**: 중복된 `push` 키는 YAML 파싱 오류 발생
- **예시**:
  ```yaml
  # ❌ 잘못됨
  push:
    branches: [dev]
  push:
    branches: [main]

  # ✅ 올바름
  push:
    branches: [dev, main]
  ```

### Python

#### DI 컨테이너 순서
- **룰**: Factory 함수는 클래스 정의 **전**에 배치
- **이유**: 클래스 본문에서 함수 참조 시 NameError 방지
- **예시**:
  ```python
  # ✅ 올바른 순서
  def _create_llm(config): ...

  class DIContainer:
      llm = providers.Singleton(_create_llm)
  ```

### 환경 변수

#### NEXT_PUBLIC_* 변수
- **룰**: `NEXT_PUBLIC_` 접두사 변수는 Secret이 아닌 Plaintext로 설정
- **이유**: 빌드 타임에 값이 필요함, Secret은 런타임에만 사용 가능
- **적용**: Vercel Dashboard → Environment Variables → Plaintext 선택

### Security

#### API Key 관리
- **룰**: 모든 API key는 GitHub Secrets에 저장, 코드에 노출 금지
- **이유**: 보안 침해 방지, 키 노출 시 revoke 필요
- **적용**:
  - `.env.example`에는 dummy 값만 포함
  - Render/Vercel 대시보드에서 직접 설정
  - GitHub Secrets: `OPENAI_API_KEY`, `GLM_API_KEY`, `TAVILY_API_KEY`

### Lint & Code Quality

#### Pre-commit Hook (필수)
- **룰**: 모든 커밋 전 pre-commit hook 실행
- **이유**: CI 실패 방지, 코드 품질 유지
- **설정**:
  ```bash
  # 설치
  pip install pre-commit

  # hook 활성화 (최초 1회)
  pre-commit install

  # 수동 실행
  pre-commit run --all-files
  ```

#### Backend - Ruff
- **룰**: Ruff linter/formatter 사용, 모든 에러 해결 후 커밋
- **이유**: Python 코드 품질 및 스타일 일관성
- **적용**:
  ```bash
  cd backend
  ruff check src/ --fix    # 자동 수정
  ruff format src/         # 포맷팅
  ```
- **주요 규칙**:
  - `B008`: Depends는 함수 파라미터 기본값에서 직접 호출 금지 → `Annotated[Type, Depends(...)]` 사용
  - `B904`: 예외 처리 시 `raise ... from e` 또는 `raise ... from None` 사용
  - `F541`: placeholder 없는 f-string 금지
  - `I001`: import 정렬 (자동 수정 가능)
  - `W293`: 빈 줄에 공백 금지 (에디터에서 자동 제거 설정)

#### Frontend - ESLint
- **룰**: ESLint 규칙 준수, any 타입 사용 최소화
- **이유**: TypeScript 타입 안정성 확보
- **적용**:
  ```bash
  cd frontend
  npm run lint      # 검사
  npm run lint:fix  # 자동 수정
  ```
- **주의사항**:
  - `any` 타입 대신 `unknown` 사용 후 타입 가드 적용
  - useEffect 내에서 직접 setState 호출 금지 → requestAnimationFrame 사용

---

*Backend AGENTS.md*
*마지막 업데이트: 2026-02-15*
