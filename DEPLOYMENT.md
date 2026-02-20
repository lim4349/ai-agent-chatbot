# 배포 가이드 (Render.com + Vercel)

> 물가 서버로 AI Agent Chatbot 배포하기

---

## 개요

| 서비스 | 용도 | 제공량 |
|--------|------|--------|
| **Render.com** | 백엔드 API | 512MB RAM, 0.1 CPU |
| **Pinecone** | 벡터 DB (RAG) | 물가 티어 |
| **Supabase** | 인증 + 세션 DB + 장기 메모리 | 물가 티어 |
| **Upstash Redis** | 단기 세션 메모리 | 물가 티어 |
| **Vercel** | 프론트엔드 | 100GB/월 트래픽 |
| **GitHub Actions** | CI/CD | 무제한 (Public repo) |

**총 비용: $0/월**

---

## 배포 프로세스

```
dev ──PR──→ main ──CD──→ [Render] + [Vercel]
```

1. `dev` 브랜치에서 개발 완료
2. `dev` → `main` PR 생성 및 머지
3. GitHub Actions 자동 배포

---

## 사전 준비

### GitHub Secrets 설정

Repository → Settings → Secrets and variables → Actions

| Secret Name | 설명 |
|-------------|------|
| `RENDER_API_KEY` | Render API 키 |
| `RENDER_BACKEND_SERVICE_ID` | 백엔드 서비스 ID |
| `RENDER_URL` | 헬스 체크용 URL |
| `VERCEL_TOKEN` | Vercel 토큰 |
| `VERCEL_ORG_ID` | Vercel 조직 ID |
| `VERCEL_PROJECT_ID` | Vercel 프로젝트 ID |
| `PINECONE_API_KEY` | Pinecone API 키 |
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_SERVICE_KEY` | Supabase Service Role Key |
| `UPSTASH_REDIS_URL` | Upstash Redis URL |
| `UPSTASH_REDIS_TOKEN` | Upstash Redis Token |

---

## Render.com 배포

### 방법 1: Blueprint (추천)

1. Render Dashboard → Blueprints → New Blueprint Instance
2. GitHub 저장소 연결
3. `render.yaml` 파일 자동 인식

### 방법 2: 수동 생성

1. Dashboard → New → Web Service
2. GitHub 저장소 선택
3. 설정:
   - **Name**: ai-agent-backend
   - **Environment**: Docker
   - **Docker Context**: ./backend
   - **Dockerfile Path**: ./backend/Dockerfile
4. Environment Variables 설정
5. Create Web Service

---

## Vercel 배포

```bash
# 1. Vercel CLI 설치
npm i -g vercel

# 2. 로그인
vercel login

# 3. 프로젝트 연결
cd frontend
vercel link

# 4. 환경 변수 설정
vercel env add NEXT_PUBLIC_API_URL
# 값: https://your-backend.onrender.com

# 5. 배포
vercel --prod
```

---

## 환경 변수 설정

### Render.com (Backend)

| 변수 | 예시 값 |
|------|---------|
| `LLM_OPENAI_API_KEY` | sk-or-v1-... (OpenRouter) |
| `LLM_BASE_URL` | https://openrouter.ai/api/v1 |
| `RAG_PINECONE_API_KEY` | xxx-xxx-xxx |
| `SUPABASE_URL` | https://xxx.supabase.co |
| `SUPABASE_SERVICE_KEY` | eyJ... |
| `UPSTASH_REDIS_URL` | rediss://default:xxx@... |
| `MEMORY_BACKEND` | redis |

### Vercel (Frontend)

| 변수 | 예시 값 |
|------|---------|
| `NEXT_PUBLIC_API_URL` | https://api.example.com |

---

## CI/CD 동작 방식

```
Push to main
    │
    ├──→ Test Backend (ruff, pytest)
    │
    ├──→ Test Frontend (npm lint, build)
    │
    ├──→ Security Scan (Trivy, npm audit)
    │
    └──→ Deploy (병렬)
         │
         ├──→ Render (Backend)
         └──→ Vercel (Frontend)
```

---

## 물가 티어 한계

1. **15분 슬립**: 15분간 요청 없으면 서버 슬립
   - 첫 요청 시 자동으로 깨어남 (10-30초 소요)

2. **512MB RAM**: 메모리 부족 주의
   - 해결책: `WEB_CONCURRENCY=1` 설정

3. **Cold Start**: 슬립 후 첫 요청 시 느림

---

## 문제 해결

### 서비스 연결 실패

```bash
# Render 로그 확인
render logs --id srv-xxxxxxxx

# 헬스 체크
curl https://your-app.onrender.com/api/v1/health
```

### Pinecone 연결 오류

- Pinecone API 키 확인 (Render Dashboard)
- `PINECONE_API_KEY`, `PINECONE_INDEX_NAME` 확인
- [Pinecone 콘솔](https://app.pinecone.io)에서 인덱스 상태 확인

---

## 참고 자료

- [Render.com 문서](https://render.com/docs)
- [Vercel 문서](https://vercel.com/docs)
- [render.yaml 참조](https://render.com/docs/blueprint-spec)

---

*마지막 업데이트: 2026-02-20*
