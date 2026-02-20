# AI Agent Chatbot - 개발 가이드

> LangGraph 기반 멀티 에이전트 챗봇 시스템

---

## 프로젝트 개요

Supervisor가 사용자 질의를 분석하여 RAG, Web Search, Code, Chat 에이전트 중 적절한 것으로 라우팅합니다.

**핵심 특징**:
- 멀티 에이전트 오케스트레이션 (LangGraph)
- RAG 파이프라인 (Pinecone + multilingual-e5-large)
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
| **LLM** | OpenRouter | Gemini/GPT-4o/Claude |
| **Vector DB** | Pinecone | - |
| **세션** | Upstash Redis / In-Memory | - |
| **배포** | Render + Vercel | - |

---

## 개발 환경 설정

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

---

## 코드 스타일

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

---

## 테스트

```bash
# 백엔드 테스트 (가상환경에서)
cd backend
source .venv/bin/activate
pytest tests/ -v

# 프론트엔드 테스트
cd frontend
npm test
```

---

## Git Workflow

```
dev (직접 커밋) → main (PR)
```

**브랜치 전략**:
- `main`: 프로덕션 브랜치 (자동 배포)
- `dev`: 개발 브랜치 (직접 커밋 가능)

**⚠️ 작업 시작 전 필수 - 브랜치 동기화**:
```bash
# 1. 원격 브랜치 최신 정보 가져오기
git fetch origin

# 2. main 브랜치 동기화
git checkout main
git pull origin main

# 3. dev 브랜치 동기화 및 main 변경사항 반영
git checkout dev
git pull origin dev
git merge origin/main  # dev가 main보다 뒤처진 경우 필수

# 4. 동기화 확인 (반드시 실행)
git log --oneline main..dev  # dev가 main보다 앞서있거나 동일해야 함
```

**간단 버전**:
```bash
git fetch origin && git checkout main && git pull origin main \
  && git checkout dev && git pull origin dev && git merge origin/main
```

**프로세스**:
```bash
# 1. dev에서 작업
git checkout dev
git pull origin dev

# 2. 작업 & 커밋
git add .
git commit -m "feat: add new feature"
git push origin dev

# 3. dev → main PR 생성 (사용자 승인 필요)
gh pr create --base main --head dev
```

**금지 사항**:
- main에 직접 commit/push 금지
- PR 생성 후 사용자 승인 없이 merge 금지
- **`dev` 브랜치 삭제 절대 금지**
  - `gh pr merge --delete-branch` 플래그 사용 금지
  - `gh pr merge <number> --merge` 만 사용

---

## 필수 규칙

**Commit 메시지**:
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

**규칙**:
- subject는 소문자로 시작
- subject 길이: 3~72자

**Pre-commit Hooks**:
```bash
# 설치 (최초 1회)
pip install pre-commit
pre-commit install

# 수동 실행
pre-commit run --all-files
```

**Git Push 전 로컬 테스트 필수**:
```bash
# 백엔드
cd backend
source .venv/bin/activate
ruff check src/

# 프론트엔드
cd frontend
npm run build
```

---

## 학습한 내용 (Lessons Learned)

### 2026-02-16

1. **Protocol 반환 타입 일치**
   - 구현체의 반환 타입을 변경하면 Protocol도 함께 수정해야 함

2. **asyncio.to_thread 사용**
   - 동기 SDK 호출은 이벤트 루프 차단 가능
   - Pinecone SDK: `await asyncio.to_thread(client.inference.embed, ...)`

3. **LLM 모델 토큰화 이슈**
   - 일부 모델이 문장 끝 punctuation 뒤 공백 없이 토큰 생성
   - 해결: `fixSentenceSpacing()` 함수로 후처리

---

## 참고 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 상세 아키텍처
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 배포 가이드
- [backend/AGENTS.md](./backend/AGENTS.md) - 백엔드 상세 가이드
- [frontend/AGENTS.md](./frontend/AGENTS.md) - 프론트엔드 상세 가이드

---

*마지막 업데이트: 2026-02-20*
