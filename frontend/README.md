# Frontend — AI Agent Chatbot

Next.js 16 기반 AI 에이전트 챗봇 프론트엔드. SSE 실시간 스트리밍, JWT 인증, XSS 방어, 다국어 지원을 포함한 프로덕션 수준 챗봇 UI.

## 소스 구조

```
src/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # 루트 레이아웃 (AuthProvider, 다크모드)
│   ├── page.tsx                  # / → /chat 리다이렉트
│   ├── chat/page.tsx             # 메인 채팅 페이지
│   └── globals.css               # Tailwind CSS 전역 스타일
│
├── components/
│   ├── chat/                     # 채팅 UI
│   │   ├── chat-container.tsx    # 채팅 컨테이너 (메시지 리스트 + 입력)
│   │   ├── chat-input.tsx        # 입력 필드 (실시간 보안 검증, 글자수 카운터)
│   │   ├── message-list.tsx      # 메시지 리스트 (자동 스크롤, 타이핑 인디케이터)
│   │   ├── message-bubble.tsx    # 메시지 버블 (아바타, 에이전트 배지, 복사)
│   │   ├── message-input.tsx     # 메시지 입력 (대체 구현)
│   │   ├── markdown-renderer.tsx # 마크다운 렌더링 (DOMPurify XSS 방어, 코드 하이라이팅)
│   │   ├── agent-badge.tsx       # 에이전트 표시 배지 (색상/아이콘/다국어)
│   │   ├── agent-switch-animation.tsx # 에이전트 전환 애니메이션
│   │   ├── tool-usage.tsx        # 도구 사용 표시 (접기/펼치기)
│   │   ├── typing-indicator.tsx  # 타이핑 인디케이터 (바운스 애니메이션)
│   │   ├── memory-indicator.tsx  # 대화 메모리 상태 표시 (토큰 사용량)
│   │   ├── memory-feedback.tsx   # 메모리 명령어 피드백 배너
│   │   ├── memory-modal.tsx      # 저장된 메모리 목록 다이얼로그
│   │   ├── memory-reference.tsx  # 이전 대화 참조 배지
│   │   ├── context-reset-button.tsx # 컨텍스트 초기화 버튼
│   │   ├── context-separator.tsx # 컨텍스트 구분선
│   │   └── summary-notification.tsx # 요약 알림
│   │
│   ├── documents/                # 문서 업로드
│   │   ├── combined-document-upload.tsx # 통합 업로드 (파일 + 텍스트 탭)
│   │   ├── file-upload-zone.tsx  # 드래그앤드롭 (react-dropzone, 매직바이트 검증)
│   │   ├── upload-progress.tsx   # 업로드 진행률 + 상태 표시
│   │   ├── document-upload.tsx   # 텍스트 업로드 (레거시)
│   │   └── document-list.tsx     # 업로드 문서 목록 + 삭제
│   │
│   ├── header/
│   │   ├── header.tsx            # 상단바 (메뉴, 타이틀, 헬스, 언어/테마 전환)
│   │   └── health-indicator.tsx  # 백엔드 상태 표시 (30초 주기)
│   │
│   ├── sidebar/
│   │   ├── sidebar.tsx           # 세션 목록 사이드바
│   │   ├── session-item.tsx      # 세션 항목 (선택, 삭제)
│   │   └── new-session-button.tsx # 새 세션 생성
│   │
│   ├── ui/                       # shadcn/ui 기반 (Radix UI)
│   │   └── badge, button, card, dialog, dropdown-menu, input, scroll-area,
│   │       separator, sheet, skeleton, tabs, textarea, toast, tooltip
│   │
│   ├── auth-provider.tsx         # 인증 초기화 + 자동 토큰 갱신 (60초 주기)
│   └── protected-route.tsx       # 인증 라우트 가드
│
├── stores/                       # Zustand 상태관리
│   ├── chat-store.ts             # 세션, 메시지, 스트리밍, 메모리 명령어
│   ├── auth-store.ts             # 인증 상태 (login, register, logout, checkAuth)
│   ├── document-store.ts         # 문서 업로드/목록/삭제 상태
│   └── toast-store.ts            # 토스트 알림 (success/info/warning/error)
│
├── lib/                          # 유틸리티 & 서비스
│   ├── api.ts                    # API 클라이언트 (JWT 자동 주입 + 401 자동 재시도)
│   ├── sse.ts                    # SSE 스트리밍 (AbortController, 토큰 필터링)
│   ├── token-manager.ts          # JWT 토큰 관리 (저장/갱신/만료 체크/자동 갱신)
│   ├── security-validator.ts     # XSS/인젝션 실시간 검증 (4단계 심각도, 한국어/영어)
│   ├── file-validation.ts        # 파일 검증 (매직바이트, 경로탐색, 확장자, 크기)
│   ├── memory-commands.ts        # 한국어 메모리 명령어 파서 (기억해/알고있니/잊어줘/요약해줘)
│   ├── i18n.ts                   # 다국어 (ko/en, Zustand + localStorage)
│   ├── constants.ts              # API URL, 에이전트 색상, 제한값, 인증 타이밍
│   └── utils.ts                  # cn() 클래스명 유틸리티
│
└── types/
    └── index.ts                  # TypeScript 타입 (Message, Session, Agent, Auth 등)
```

## 설치 및 실행

```bash
# 의존성 설치
npm install

# 환경변수
cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000  (기본값)

# 개발 서버
npm run dev     # http://localhost:3000

# 프로덕션 빌드
npm run build
npm start
```

## 주요 기능

### 실시간 채팅
- SSE (Server-Sent Events) 기반 토큰 스트리밍
- **토큰 버퍼링**: 50ms 간격 또는 100자 초과 시 플러시 (렌더링 최적화)
- 스트리밍 중 plain text, 완료 후 마크다운 렌더링 (성능 최적화)
- 자동 스크롤 + "아래로" 버튼 (스크롤 위치 감지)

### 에이전트 시각화
- 에이전트별 색상 배지 (Chat: 초록, Code: 보라, RAG: 파랑, WebSearch: 주황)
- 에이전트 전환 애니메이션 (Framer Motion)
- 도구 사용 내역 접기/펼치기 표시
- 이전 대화 참조 배지 (메모리 기반)

### 문서 업로드
- 드래그 앤 드롭 파일 업로드 (react-dropzone)
- 파일 + 텍스트 붙여넣기 2가지 모드
- 실시간 파일 검증 (매직바이트, 크기, 타입, 경로탐색)
- 업로드 진행률 표시 + 상태 배지
- 지원 형식: PDF, DOCX, TXT, MD, CSV, JSON (최대 10MB)

### 메모리 명령어 (한국어)
| 명령어 | 예시 | 동작 |
|--------|------|------|
| `기억해:` | "기억해: 나는 파이썬 개발자야" | 사용자 정보 저장 |
| `알고 있니?` | "내 이름 알고 있니?" | 저장된 메모리 조회 |
| `잊어줘:` | "잊어줘: 나이 정보" | 메모리 삭제 |
| `요약해줘` | "대화 요약해줘" | 대화 요약 생성 |

### 보안
- **XSS 방어**: DOMPurify 태그/속성 화이트리스트, URL 프로토콜 검증
- **입력 검증**: 4단계 심각도 (critical/error/warning/info), 패턴 목록 표시
- **파일 검증**: 매직바이트, 경로 탐색 방지, 의심 확장자 차단
- **JWT**: sessionStorage 우선, 만료 60초 전 자동 갱신, 401 자동 재시도

### 다국어 (i18n)
- 한국어 / 영어 전환
- 헤더 토글 버튼으로 즉시 변경
- localStorage에 설정 유지
- 보안 경고, 에이전트 이름, UI 텍스트 전체 번역

## 컴포넌트 계층

```
RootLayout (layout.tsx)
└── AuthProvider (인증 초기화 + 토큰 갱신 루프)
    └── TooltipProvider
        └── ChatPage (chat/page.tsx)
            ├── Header
            │   ├── HealthIndicator (30초 주기 헬스 체크)
            │   ├── 언어 토글 (EN/한)
            │   └── 테마 토글 (라이트/다크)
            ├── Sidebar (데스크톱: 상시 / 모바일: Sheet)
            │   ├── NewSessionButton
            │   └── SessionItem[] (선택, 삭제)
            └── Main
                ├── CombinedDocumentUpload (다이얼로그)
                └── ChatContainer
                    ├── MessageList
                    │   ├── MessageBubble[]
                    │   │   ├── AgentBadge
                    │   │   ├── AgentSwitchAnimation
                    │   │   ├── MarkdownRenderer (또는 plain text)
                    │   │   ├── ToolUsage (접기/펼치기)
                    │   │   └── MemoryReference
                    │   └── TypingIndicator
                    └── ChatInput
                        ├── Textarea (Enter 전송, Shift+Enter 줄바꿈)
                        ├── 글자수 카운터 (2000자 제한)
                        └── SecurityWarning 배너
```

## 상태관리 (Zustand)

### chat-store
- `sessions[]`, `activeSessionId` — 세션 관리
- `isStreaming` — 스트리밍 상태
- `sendMessage(content)` — SSE 스트리밍 + 토큰 버퍼링
- 메모리 명령어 파싱 및 피드백
- localStorage 영속화 (sessions, activeSessionId, memories)

### auth-store
- `login()`, `register()`, `logout()`, `checkAuth()`
- JWT 토큰 기반 인증 상태 관리
- localStorage 영속화 (user)

### document-store
- `uploadFile()` — 파일 검증 + 업로드 + 진행률
- `fetchDocuments()`, `deleteDocument()`
- 영속화 없음 (매번 서버에서 가져옴)

## 성능 최적화

1. **토큰 버퍼링**: 50ms 간격 배치 플러시로 렌더링 횟수 최소화
2. **스트리밍 시 plain text**: 마크다운 파싱 건너뛰어 CPU 부하 감소
3. **스크롤 디바운싱**: 150ms 디바운스 + RAF 사용
4. **코드블록 접기**: 30줄 이상 자동 접기
5. **Memoized 컴포넌트**: 완료된 메시지 블록 메모이제이션

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | 백엔드 API URL |

## 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| Next.js | 16.1.6 | React 프레임워크 (App Router) |
| React | 19.2.3 | UI 라이브러리 |
| TypeScript | 5.x | 타입 안전성 |
| Tailwind CSS | 4.x | 유틸리티 기반 스타일링 |
| Zustand | 5.0.11 | 클라이언트 상태관리 |
| Radix UI | 1.4.3 | 접근성 준수 UI 프리미티브 |
| react-markdown | 10.1.0 | 마크다운 렌더링 |
| DOMPurify | 3.3.1 | XSS 방어 |
| highlight.js | 11.11.1 | 코드 구문 하이라이팅 |
| Framer Motion | 12.34.0 | 애니메이션 |
| react-dropzone | 15.0.0 | 파일 드래그앤드롭 |
| Lucide React | 0.564.0 | 아이콘 |

## 상세 문서

- [XSS 방어 구현](./XSS_PROTECTION.md) — DOMPurify 설정, URL 검증, 위협 모델
