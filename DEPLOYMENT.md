# 배포 가이드 (Render.com + Vercel)

> 묣가 티어(Free Tier)로 AI Agent Chatbot 배포하기

---

## 개요

이 프로젝트는 다음 무료 서비스들로 구성됩니다:

| 서비스 | 용도 | 제공량 |
|--------|------|--------|
| **Render.com** | 백엔드 API | 512MB RAM, 0.1 CPU |
| **Pinecone** | 벡터 DB + 세션 저장소 | 무료 티어 |
| **Vercel** | 프론트엔드 | 100GB/월 트래픽 |
| **GitHub Actions** | CI/CD | 무제한 (Public repo) |

**총 비용: $0/월**

---

## Git Flow 배포 프로세스

이 프로젝트는 **Git Flow**를 따릅니다:

```
feature/my-feature  ──PR──→  dev  ──PR──→  main
     │                      │              │
     ▼                      ▼              ▼
 CI (테스트/린트)      CI (최종 확인)   CD (자동 배포)
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                     [Pinecone]        [Backend]         [Frontend]
```

### 브랜치 전략

| 브랜치 | 용도 | 보호 규칙 |
|--------|------|-----------|
| `main` | 프로덕션 | PR 필수, CI 통과 필수 |
| `dev` | 개발 통합 | PR 필수 |
| `feature/*` | 기능 개발 | - |
| `fix/*` | 버그 수정 | - |
| `docs/*` | 문서 수정 | - |

### PR 워크플로우

1. **작업 브랜치 생성**: `git checkout -b feature/my-feature`
2. **코드 작성 및 커밋**: `git commit -m "feat: ..."`
3. **dev에 PR 생성**: `gh pr create --base dev`
4. **CI 자동 실행**: 테스트, 린트, 보안 스캔
5. **코드 리뷰**: 팀원 리뷰 및 승인
6. **dev에 머지**: `dev` 브랜치로 머지
7. **main에 PR 생성**: `gh pr create --base main --head dev`
8. **main에 머지**: CD 자동 실행 → 프로덕션 배포

---

## 사전 준비

### 1. GitHub Secrets 설정

Repository → Settings → Secrets and variables → Actions → New repository secret

| Secret Name | 값 | 설명 |
|-------------|-----|------|
| `RENDER_API_KEY` | rdp_xxxxxxxx | Render API 키 |
| `RENDER_BACKEND_SERVICE_ID` | srv-xxxxxxxx | 백엔드 서비스 ID |
| `RENDER_URL` | https://your-app.onrender.com | 헬스 체크용 URL |
| `VERCEL_TOKEN` | xxxxxxxx | Vercel 토큰 |
| `VERCEL_ORG_ID` | team_xxxxxxxx | Vercel 조직 ID |
| `VERCEL_PROJECT_ID` | prj_xxxxxxxx | Vercel 프로젝트 ID |
| `PINECONE_API_KEY` | xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | Pinecone API 키 |

---

## Render.com 배포 방법

### 방법 1: Blueprint로 한 번에 생성 (추천)

1. Render Dashboard → Blueprinters → New Blueprint Instance
2. GitHub 저장소 연결
3. `render.yaml` 파일이 자동으로 인식됨
4. 다음 서비스가 생성됨:
   - `ai-agent-backend` (웹 서비스)

### 방법 2: 수동으로 서비스 생성

#### Backend 서비스
1. Dashboard → New → Web Service
2. GitHub 저장소 선택
3. 설정:
   - **Name**: ai-agent-backend
   - **Environment**: Docker
   - **Docker Context**: ./backend
   - **Dockerfile Path**: ./backend/Dockerfile
4. Environment Variables 설정
5. Create Web Service

#### Pinecone 설정
1. [Pinecone 콘솔](https://app.pinecone.io)에서 계정 생성
2. 새 인덱스 생성:
   - **Index Name**: ai-agent-index
   - **Dimensions**: 1024 (multilingual-e5-large)
   - **Metric**: cosine
3. API Key 발급 및 Render Environment Variables에 추가

---

## Vercel 배포 방법

### 1. Vercel CLI 설치 및 로그인

```bash
npm i -g vercel
vercel login
```

### 2. 프로젝트 연결

```bash
cd frontend
vercel link
```

### 3. 환경 변수 설정

```bash
vercel env add NEXT_PUBLIC_API_URL
# 값: https://your-backend.onrender.com
```

### 4. 수동 배포

```bash
vercel --prod
```

---

## 환경 변수 설정

### Render.com (Backend)

| 변수 | 예시 값 | 설명 |
|------|---------|------|
| `OPENAI_API_KEY` | sk-... | OpenAI API 키 |
| `ANTHROPIC_API_KEY` | sk-ant-... | Anthropic API 키 |
| `TAVILY_API_KEY` | tvly-... | Tavily 검색 API |
| `PINECONE_API_KEY` | xxx-xxx-xxx | Pinecone API 키 |
| `PINECONE_INDEX_NAME` | ai-agent-index | Pinecone 인덱스 이름 |
| `EMBEDDING_PROVIDER` | pinecone | 임베딩 제공자 (pinecone/openai) |
| `MEMORY_BACKEND` | in_memory | 메모리 백엔드 (in_memory/pinecone) |

### Vercel (Frontend)

| 변수 | 예시 값 | 설명 |
|------|---------|------|
| `NEXT_PUBLIC_API_URL` | https://api.example.com | 백엔드 API URL |

---

## CI/CD 동작 방식

```
Push to main
    │
    ├──→ Test Backend (pytest, ruff, mypy)
    │
    ├──→ Test Frontend (npm test, build)
    │
    ├──→ Security Scan (Trivy, npm audit)
    │
    └──→ Deploy (병렬)
         │
         ├──→ Render
         │   └──→ Deploy Backend
         │
         └──→ Vercel
              └──→ Deploy Frontend
```

---

## 주의사항

### 묣가 티어 한계

1. **15분 슬립**: 15분간 요청 없으면 서버 슬립
   - 첫 요청 시 자동으로 깨어남 (10-30초 소요)

2. **512MB RAM**: 메모리 부족 주의
   - 해결책: `WEB_CONCURRENCY=1` 설정

3. **Cold Start**: 슬립 후 첫 요청 시 느림 (10-30초)

### 서비스 의존성

- Backend는 Pinecone API에 의존
- Pinecone은 외부 SaaS로 별도 배포 불필요

---

## 문제 해결

### 서비스 연결 실패

```bash
# Render 로그 확인
render logs --id srv-xxxxxxxx

# 서비스 상태 확인
curl https://your-app.onrender.com/api/v1/health
```

### Pinecone 연결 오류

```bash
# Pinecone API 키 확인 (Render Dashboard Environment Variables)
# PINECONE_API_KEY, PINECONE_INDEX_NAME 확인

# Pinecone 콘솔에서 인덱스 상태 확인
# https://app.pinecone.io
```

---

## 참고 자료

- [Render.com 문서](https://render.com/docs)
- [Vercel 문서](https://vercel.com/docs)
- [render.yaml 참조](https://render.com/docs/blueprint-spec)

---

*배포 가이드*
*마지막 업데이트: 2026-02-16*
