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
- 영구 세션 메모리 (Upstash Redis)

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
| **Session** | Upstash Redis (프로덕션) / In-Memory (로컬) | - |
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

### 4. Git Workflow (필수 준수)

```
{feat|fix|docs}/* → dev → main
```

**브랜치 전략**:
- `main`: 프로덕션 브랜치 (자동 배포)
- `dev`: 개발 통합 브랜치
- `feat/*`: 기능 개발 브랜치
- `fix/*`: 버그 수정 브랜치
- `docs/*`: 문서 수정 브랜치

**⚠️ 필수 프로세스**:
```
1. feat/xxx 브랜치 생성
2. 작업 완료 후 feat/xxx → dev PR 생성
3. dev에서 테스트 & 리뷰 통과 후 merge
4. dev → main PR 생성
5. main merge 시 자동 배포
```

**금지 사항**:
- ❌ dev에 직접 commit/push 금지
- ❌ main에 직접 commit/push 금지
- ❌ feat 브랜치 없이 작업 금지
- ❌ PR 생성 후 사용자 승인 없이 merge 금지 (반드시 사용자의 최종 승인 후 merge 진행)

**올바른 예시**:
```bash
# 1. feature 브랜치 생성
git checkout dev
git pull origin dev
git checkout -b feat/pinecone-embedding

# 2. 작업 & 커밋
git add .
git commit -m "feat: Add Pinecone embedding support"

# 3. 푸시 & PR (→ dev)
git push origin feat/pinecone-embedding
gh pr create --base dev --head feat/pinecone-embedding

# 4. dev merge 후 main PR
gh pr create --base main --head dev
```

### 5. ⚠️ 필수 규칙

**Commit 메시지 형식 (commitlint.config.js 준수)**:
```
<type>: <subject>

[optional body]
```

**허용 타입**:
- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `style`: 코드 스타일 변경
- `refactor`: 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드/보조 도구 변경
- `build`: 빌드 시스템 변경
- `ci`: CI 설정 변경
- `perf`: 성능 개선
- `revert`: 이전 커밋 되돌리기
- `release`: 릴리즈

**규칙**:
- subject는 소문자로 시작
- subject 길이: 3~72자
- 예: `feat: Add user authentication`

**Pre-commit Hooks (.pre-commit-config.yaml)**:
```bash
# 설치 (최초 1회)
pip install pre-commit
pre-commit install

# 수동 실행
pre-commit run --all-files
```

**실행되는 검사**:
- Backend: Ruff lint + format
- Frontend: ESLint
- 공통: trailing whitespace, EOF, YAML/JSON 검사

**모든 작업 전 git pull 필수**:
```bash
# 원격 변경사항 최신화
git fetch origin
git checkout dev && git pull origin dev
# 또는 현재 브랜치에서
git pull
```
- 로컬/원격 브랜치 모두 항상 최신 상태 유지
- 작업 시작 전 반드시 pull로 동기화

**Git Push 전 로컬 테스트 필수**:
```bash
# 백엔드 (가상환경에서)
cd backend
source .venv/bin/activate
ruff check src/                    # 린트 체크
python -c "from src.xxx import yyy" # import 테스트

# 프론트엔드
cd frontend
npm run build                      # 빌드 테스트
```

**PR Review 피드백은 CLAUDE.md에 추가**:
- 새로운 에러 패턴 발견 시 이 문서에 기록
- 코드 컨벤션/패턴 학습 내용 추가

---

## 학습한 내용 (Lessons Learned)

### 2026-02-16

1. **Protocol 반환 타입 일치**
   - 구현체의 반환 타입을 변경하면 Protocol도 함께 수정해야 함
   - `dict` → `dict | None` 변경 시 `protocols.py`도 업데이트

2. **validate_file_upload 반환값**
   - 반환하는 metadata에는 `detected_type` 키 사용 (not `extension`)
   - `file_metadata.get("detected_type")`로 접근

3. **asyncio.to_thread 사용**
   - 동기 SDK 호출은 이벤트 루프 차단 가능
   - Pinecone SDK: `await asyncio.to_thread(client.inference.embed, ...)`

4. **문서 업로드 UX**
   - 상태 확인 후 모달 닫기: `uploadStatus === 'completed'` 체크
   - 에러 시 모달 유지 필요

5. **GLM 모델 토큰화 이슈**
   - GLM 모델이 문장 끝 punctuation 뒤 공백 없이 토큰 생성
   - 해결: `fixSentenceSpacing()` 함수로 후처리
   - 패턴: `/([.!?。！？])([A-Za-z가-힣])/g` → `$1 $2`

6. **SSE JSON 이스케이핑**
   - heredoc으로 JSON 생성 시 특수 문자로 파싱 에러
   - 해결: `jq -Rs` 사용하여 안전하게 JSON 생성

7. **threading.Lock for thread-safe dict**
   - FastAPI는 비동기지만 글로벌 dict 접근 시 race condition 가능
   - `threading.Lock`으로 보호 (임시 방편, DB 마이그레이션 권장)

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
- [commitlint.config.js](./commitlint.config.js) - 커밋 메시지 규칙
- [.pre-commit-config.yaml](./.pre-commit-config.yaml) - Pre-commit hooks

---

*마지막 업데이트: 2026-02-16*

PR 제목과 변경사항을 바탕으로 `CLAUDE.md`를 업데이트해야 합니다.

변경사항을 분석해보면 두 가지 주요 내용이 있습니다:
1. **Workflow 개선**: `CLAUDE.md` 업데이트 로직 자동화
2. **새로운 규칙 추가**: PR 생성 후 즉시 merge 금지

현재 `CLAUDE.md` diff에는 이미 규칙이 추가되어 있으므로, 이 내용을 규칙 섹션에 반영하면 됩니다.

```markdown

### 2026-02-17 (PR #26)

제공해주신 PR 내용(`fix: Mobile UI improvements`)과 실제 코드 변경사항(diff)을 분석한 결과, **PR 제목과 실제 내용이 일치하지 않는 것으로 보입니다.**

실제 변경사항은 모바일 UI 개선이 아니라, **백엔드 Python 코드의 린트(Lint) 포맷팅 수정**입니다. 따라서 `claude.md` 파일 업데이트뿐만 아니라 PR 제목 수정도 강력히 권장합니다.

다음은 `claude.md` 파일에 반영해야 할 업데이트 내용과 구체적인 개선 제안입니다.

---

### 1. 분석 결과

*   **PR 제목:** `fix: Mobile UI improvements - menu, scroll, and sidebar` (모바일 UI 수정)
*   **실제 변경 내용:**
    *   백엔드 파이썬 코드 포맷팅 (Black/Ruff 적용 추정)
    *   `isinstance(obj, (A, B))` 구문을 `isinstance(obj, A | B)` (Python 3.10+ 스타일)로 변경
    *   `.github/workflows/ci-cd.yml` 파일의 공백(Whitespace) 수정
*   **결론:** 문서 수정 내용 없음. **PR 제목을 백엔드 스타일 수정 관련 내용으로 변경**해야 합니다.

### 2. `claude.md` 업데이트 제안

이번 변경사항은 기능적 변화가 없는 **스타일(Style) 및 정리(Chore)** 작업입니다. `claude.md` 파일에 아래 내용을 추가하여 프로젝트의 코딩 컨벤션을 명시하는 것이 좋습니다.

```markdown
# Claude.md (Update Proposal)

## Backend Code Style
- **Python Version**: 3.10+
- **Type Unions**: Use the `A | B` syntax instead of `typing.Union[A, B]` or `isinstance(x, (A, B))`.
  - *Good:* `isinstance(node, ast.Import | ast.ImportFrom)`
  - *Bad:* `isinstance(node, (ast.Import, ast.ImportFrom))`
- **Formatting**: Follow Ruff/Black formatting standards (e.g., trailing commas in multiline lists, line breaks for long function signatures).

## CI/CD
- Maintain consistent indentation (workflow files cleaned up).
```

---

### 3. 구체적인 개선 제안 (Action Items)

이 PR을 머지하기 전에 다음 사항들을 처리할 것을 제안합니다.

#### 1) PR 제목 및 설명 변경 (필수)
현재 PR 제목은 "Mobile UI improvements"이지만, 변경된 코드는 전혀 다른 내용입니다. 리뷰어와 협업자에게 혼란을 주지 않도록 제목을 수정하세요.
*   **추천 제목:** `chore(backend): Apply Python 3.10+ style and lint formatting` 또는 `style: Refactor backend code for consistency`

#### 2) Python 3.10+ 문법 적용 (`backend/src/core/validators.py` 등)
변경사항에서 `isinstance(value, (int, float, bool))`를 `int | float | bool`로 변경한 부분이 있습니다. 이는 Python 3.10 이상에서 권장되는 문법이므로 매우 좋은 변경입니다.
*   **제안:** 프로젝트 전체에 걸쳐 `typing.Union`이나 튜플 방식의 `isinstance`를 `|` 연산자로 통일했는지 확인하세요. (해당 PR에서 일관성 있게 적용된 것으로 보입니다.)

#### 3) CI/CD 파일의 불필요한 변경 주의 (`.github/workflows/ci-cd.yml`)
diff를 보면 코드 로직 변경 없이 빈 줄(Blank lines)만 수정된 부분이 많습니다.
*   **제안:** 에디터의 "Trim Trailing Whitespace" 설정이나 포매터가 자동으로 수정한 것으로 보입니다. 중요한 변경은 아니지만, Git history를 더럽히지 않기 위해 향후에는 포맷팅 수정과 기능 수정을 분리해서 커밋하는 것이 좋습니다.

### 요약
`claude.md` 업데이트 요청에 따라 **"백엔드 코드 스타일을 Python 3.10+ 표준(`A | B`)으로 통일함"**이라는 내용을 추가하시고, **PR 제목을 실제 내용에 맞게 수정**해주시기 바랍니다.
