# Backend AGENTS.md

> FastAPI 백엔드 개발 실전 가이드

---

## 핵심 패턴

### 1. DI 컨테이너와 @inject 사용

**의존성 주입은 `dependency-injector` 라이브러리를 사용합니다.**

```python
from dependency_injector import containers, providers
from dependency_injector.wiring import inject, Provide

class DIContainer(containers.DeclarativeContainer):
    config = providers.Singleton(get_config)
    llm = providers.Factory(_create_llm, config=config.provided.llm)
    memory = providers.Factory(_create_memory, config=config.provided.memory)
```

**FastAPI Routes에서 사용:**
```python
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

**Agent 클래스에서 사용:**
```python
class SupervisorAgent:
    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        memory: MemoryStore = Provide[DIContainer.memory],
    ):
        self.llm = llm
        self.memory = memory
```

**팁:** Factory 함수는 클래스 정의 **전**에 배치하세요 (NameError 방지)

---

### 2. Protocol 기반 설계

**상속 없이 인터페이스 정의:**

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, messages: list[dict[str, str]], **kwargs) -> str: ...

# 상속 없이 구현
class OpenAIProvider:
    async def generate(self, messages, **kwargs) -> str:
        return response
```

**주의:** Protocol 반환 타입을 변경하면 모든 구현첼도 함께 수정해야 합니다.

---

### 3. 테스트에서 의존성 오버라이드

```python
import pytest
from src.core.di_container import di_container

@pytest.fixture
def test_container(mock_llm, mock_memory):
    # 테스트용으로 의존성 오버라이드
    di_container.llm.override(providers.Object(mock_llm))
    di_container.memory.override(providers.Object(mock_memory))

    yield di_container

    # 테스트 후 초기화
    di_container.reset_singletons()
```

---

## 프로젝트 룰

> PR 리뷰에서 발견된 반복적인 패턴과 규칙

### Python 코드 품질

#### Ruff 린터 규칙

```bash
cd backend
ruff check src/ --fix    # 자동 수정
ruff format src/         # 포맷팅
```

**주요 규칙:**
- `B008`: Depends는 함수 파라미터 기본값에서 직접 호출 금지 → `Annotated[Type, Depends(...)]` 사용
- `B904`: 예외 처리 시 `raise ... from e` 또는 `raise ... from None` 사용
- `F541`: placeholder 없는 f-string 금지
- `I001`: import 정렬 (자동 수정 가능)

#### 비동기 처리

```python
# 동기 SDK는 asyncio.to_thread로 감싸기
import asyncio

# ❌ 이벤트 루프 차단
embedding = client.inference.embed(...)

# ✅ 별도 스레드에서 실행
embedding = await asyncio.to_thread(client.inference.embed, ...)
```

---

### 파일 업로드 보안

```python
# validate_file_upload 반환값 사용
metadata = validate_file_upload(file)
# metadata에는 detected_type 키 사용 (not extension)
type = metadata.get("detected_type")
```

---

### 환경 변수

- `.env.example`에는 dummy 값만 포함
- 실제 값은 Render/Vercel 대시보드에서 직접 설정
- `NEXT_PUBLIC_*` 변수는 Secret이 아닌 Plaintext로 설정 (빌드 타임에 필요)

---

### 테스트 전략

```bash
# CI에서는 unit 테스트만 (timeout 주의)
pytest tests/unit -v --timeout=60

# Integration 테스트는 로컬에서만
export OPENAI_API_KEY=xxx
pytest tests/integration -v
```

---

### Git Workflow

**브랜치 전략:**
```
feat/xxx → dev (CI) → main (CD)
```

**금지 사항:**
- `main`에 직접 push 금지
- `dev` 브랜치 삭제 절대 금지

**작업 전 필수 동기화:**
```bash
git fetch origin
git checkout main && git pull origin main
git checkout dev && git pull origin dev
git merge origin/main  # dev가 main보다 뒤처진 경우 필수
```

---

## 개발 서버 실행

```bash
# 가상환경 활성화 (필수!)
source .venv/bin/activate

# 개발 모드
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

---

*Backend AGENTS.md - 실전 개발 가이드*
</content>
</invoke>