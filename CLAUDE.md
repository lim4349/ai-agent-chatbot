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
## 학습한 내용 (Lessons Learned)

---

### 2025-01-14 (PR #해당PR번호)

**새로운 규칙 추가**: PR 생성 후 즉시 merge 금지

- Claude는 PR을 생성한 후 사용자의 승인(approve) 없이 merge해서는 안 됩니다.
- 워크플로우:
  1. `feat/` 브랜치에서 작업
  2. PR 생성
  3. **사용자 승인 대기** (필수)
  4. 승인 후 merge

**Workflow 개선사항**:
- `CLAUDE.md` 업데이트 트리거 키워드 확장: `update claude.md`, `기억`, `learn`, `save`, `저장`
- "학습한 내용 (Lessons Learned)" 섹션에 자동으로 추가되도록 개선
- 커밋 메시지 형식 통일: `docs: Add Claude review insights to CLAUDE.md [skip ci]`
```

---

**구체적인 개선 제안**:

1. **Workflow 키워드 일관성**: 현재 `기억|learn|save|저장` 패턴이 있는데, 한글/영어 혼용입니다. 문서화에 명확한 사용법을 추가하면 좋습니다:
   - `@claude update claude.md` 또는 `@claude 이 내용을 기억해`

2. **중복 방지 로직**: 같은 내용이 여러 번 추가되는 것을 방지하기 위해 해시나 ID 기반 체크를 추가하는 것을 고려해보세요.

3. **규칙 섹션 구조화**: 금지 사항을 더 명확하게 그룹화:
   ```markdown
   ### 브랜치 및 PR 규칙
   - ❌ dev/main에 직접 commit/push 금지
   - ❌ feat 브랜치 없이 작업 금지
   - ❌ PR 생성 후 즉시 merge 금지 (사용자 승인 필수)
   ```

이 PR을 승인하시겠습니까?
