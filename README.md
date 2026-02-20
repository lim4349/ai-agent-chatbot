# AI Agent Chatbot

LangGraph 기반 Multi-Agent 챗봇 시스템. Supervisor 패턴으로 4개 전문 에이전트를 오케스트레이션합니다.

## 데모

**체험하기**: [https://ai-agent-chatbot-iota.vercel.app/chat](https://ai-agent-chatbot-iota.vercel.app/chat)

> **묣가 티어 운영**: 일일 요청 제한 50회. 제한 도달 시 다음 날 자동 초기화됩니다.

> **Cold start**: 우측 상단 빨간불이 떴다면 서버가 연결되서 초록불이 될 때까지 잠시 대기해주세요.

---

## 사용 방법

### 채팅 모드

1. 일반 질문: 자유롭게 질문하면 Supervisor가 적절한 에이전트로 라우팅합니다
2. 문서 기반 Q&A: PDF/DOCX 업로드 후 문서에 대해 질문 (RAG 에이전트)
3. 웹 검색: 실시간 정보가 필요한 질문 (Web Search 에이전트)
4. 코드 작성: 프로그래밍 관련 질문 (Code 에이전트)

### 메모리 명령

| 명령 | 예시 | 설명 |
|------|------|------|
| `기억해:` | `기억해: 나는 커피를 좋아해` | 사용자 정보 저장 |
| `알고 있니?` | `내가 좋아하는 게 뭐야?` | 저장된 메모리 검색 |
| `잊어줘:` | `잊어줘: 커피` | 메모리 삭제 |
| `요약해줘` | `지금까지 대화 요약해줘` | 즉시 요약 생성 |

### 문서 업로드

- 지원 형식: PDF, DOCX, TXT, MD, CSV, JSON
- 최대 크기: 10MB
- 업로드 후 자동으로 문서 내용을 기반으로 질문 가능

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| **프론트엔드** | Next.js 16 + TypeScript + Tailwind CSS 4 + Zustand |
| **백엔드** | Python 3.12 + FastAPI |
| **AI 오케스트레이션** | LangGraph + LangChain |
| **LLM** | OpenRouter (Gemini Flash / GPT-4o / Claude) |
| **Vector DB** | Pinecone (multilingual-e5-large 임베딩) |
| **세션 메모리** | Upstash Redis (프로덕션) / In-Memory (로컬) |
| **인증** | Supabase Auth |
| **배포** | Render (백엔드) + Vercel (프론트엔드) |

---

## 프로젝트 구조

```
ai-agent-chatbot/
├── backend/           # FastAPI + LangGraph
│   ├── src/
│   │   ├── agents/    # 멀티 에이전트 시스템 (Chat, RAG, WebSearch, Code)
│   │   ├── api/       # REST API
│   │   ├── core/      # DI 컨테이너, 설정, 보안
│   │   ├── documents/ # 문서 처리 (파서, 청커)
│   │   ├── graph/     # LangGraph 상태 머신
│   │   ├── llm/       # LLM 프로바이더
│   │   └── memory/    # 메모리 저장소
│   └── tests/
│
├── frontend/          # Next.js
│   ├── src/
│   │   ├── app/       # App Router
│   │   ├── components/# React 컴포넌트
│   │   ├── lib/       # 유틸리티
│   │   └── stores/    # Zustand 상태관리
│   └── package.json
│
├── ARCHITECTURE.md    # 아키텍처 문서
├── DEPLOYMENT.md      # 배포 가이드
└── README.md          # 프로젝트 소개
```

---

## 문서

- [아키텍처 문서](./ARCHITECTURE.md) — 시스템 설계 및 아키텍처 상세
- [배포 가이드](./DEPLOYMENT.md) — Render.com + Vercel 배포 방법

---

## 라이선스

MIT
