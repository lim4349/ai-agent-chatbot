# Frontend AGENTS.md

> Next.js 16 + TypeScript AI Chatbot 프론트엔드 개발 가이드

---

## 개요

Next.js 16 App Router 기반의 AI 챗봇 프론트엔드. 실시간 스트리밍 응답(SSE)과 반응형 UI를 제공합니다.

---

## 기술 스택

| 구성 요소 | 기술 | 용도 |
|-----------|------|------|
| **Framework** | Next.js 16.1.6 | React + SSR + API Routes |
| **Language** | TypeScript 5.x | 타입 안전성 |
| **Styling** | Tailwind CSS 4.x | 유틸리티 CSS |
| **Components** | shadcn/ui + Radix UI | 기본 UI 컴포넌트 |
| **State** | Zustand 5.0.11 | 전역 상태 관리 |
| **Animation** | Framer Motion 12.34.0 | UI 애니메이션 |
| **Icons** | Lucide React 0.564.0 | 아이콘 라이브러리 |
| **Markdown** | react-markdown 10.1.0 | 마크다운 렌더링 |
| **Security** | DOMPurify 3.3.1 | XSS 방어 |
| **Upload** | react-dropzone 15.0.0 | 파일 드래그앤드롭 |

---

## 프로젝트 구조

```
frontend/
├── src/
│   ├── app/                     # Next.js App Router
│   │   ├── page.tsx             # 메인 페이지 (/)
│   │   ├── chat/                # 채팅 페이지 (/chat)
│   │   │   └── page.tsx
│   │   ├── layout.tsx           # 루트 레이아웃
│   │   └── globals.css          # 전역 스타일
│   │
│   ├── components/              # React 컴포넌트
│   │   ├── chat/                # 채팅 관련
│   │   │   ├── message-list.tsx
│   │   │   ├── message-input.tsx
│   │   │   └── chat-bubble.tsx
│   │   ├── documents/           # 문서 업로드
│   │   │   ├── file-upload-zone.tsx
│   │   │   └── upload-progress.tsx
│   │   └── ui/                  # shadcn/ui 컴포넌트
│   │       ├── button.tsx
│   │       ├── dialog.tsx
│   │       └── ...
│   │
│   ├── lib/                     # 유틸리티
│   │   ├── api.ts               # API 클라이언트
│   │   ├── utils.ts             # 헬퍼 함수
│   │   ├── file-validation.ts   # 파일 검증
│   │   └── token-manager.ts     # JWT 관리
│   │
│   ├── stores/                  # Zustand 상태
│   │   ├── chat-store.ts        # 채팅 상태
│   │   ├── document-store.ts    # 문서 상태
│   │   └── auth-store.ts        # 인증 상태
│   │
│   └── types/                   # TypeScript 타입
│       └── index.ts
│
├── components.json              # shadcn/ui 설정
├── tailwind.config.ts
├── next.config.js
└── package.json
```

---

## 개발 가이드

### 1. 환경 설정

```bash
# Node.js 20+ 권장
node -v  # v20.x.x

# 의존성 설치
npm install

# 환경 변수
cp .env.local.example .env.local
# .env.local 편집
```

### 2. 개발 서버

```bash
# 개발 모드
npm run dev

# 빌드 테스트
npm run build

# 프로덕션 모드
npm start
```

### 3. 코드 품질

```bash
# 린트
npm run lint

# 린트 자동 수정
npm run lint:fix

# 타입 체크
npx tsc --noEmit
```

### 4. 테스트

```bash
# 테스트 실행
npm test

# 테스트 감시 모드
npm test -- --watch

# 커버리지
npm test -- --coverage
```

---

## 컴포넌트 개발

### 새로운 컴포넌트

```tsx
// src/components/my-feature/my-component.tsx
"use client";  // 클라이언트 컴포넌트 필요 시

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface MyComponentProps {
  title: string;
  onAction: () => void;
}

export function MyComponent({ title, onAction }: MyComponentProps) {
  const [count, setCount] = useState(0);

  return (
    <div className="p-4 border rounded-lg">
      <h2 className="text-lg font-bold">{title}</h2>
      <p className="text-muted-foreground">Count: {count}</p>
      <div className="flex gap-2 mt-4">
        <Button onClick={() => setCount(c => c + 1)}>
          Increment
        </Button>
        <Button variant="outline" onClick={onAction}>
          Action
        </Button>
      </div>
    </div>
  );
}
```

### shadcn/ui 컴포넌트 추가

```bash
# 새 컴포넌트 설치
npx shadcn add button
npx shadcn add dialog
npx shadcn add dropdown-menu

# 사용
import { Button } from "@/components/ui/button";
```

---

## 상태 관리 (Zustand)

### 새로운 Store

```typescript
// src/stores/my-store.ts
import { create } from "zustand";

interface MyState {
  // State
  data: string[];
  isLoading: boolean;

  // Actions
  setData: (data: string[]) => void;
  addItem: (item: string) => void;
  fetchData: () => Promise<void>;
}

export const useMyStore = create<MyState>((set, get) => ({
  data: [],
  isLoading: false,

  setData: (data) => set({ data }),

  addItem: (item) => set((state) => ({
    data: [...state.data, item]
  })),

  fetchData: async () => {
    set({ isLoading: true });
    try {
      const response = await fetch("/api/data");
      const data = await response.json();
      set({ data });
    } finally {
      set({ isLoading: false });
    }
  },
}));

// 사용
const { data, isLoading, fetchData } = useMyStore();
```

---

## API 통신

### API 클라이언트

```typescript
// src/lib/api.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  async chat(message: string, sessionId?: string) {
    const response = await fetch(`${API_URL}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    if (!response.ok) {
      throw new Error("Failed to send message");
    }

    return response.json();
  },

  // SSE 스트리밍
  async *chatStream(message: string, sessionId?: string) {
    const response = await fetch(`${API_URL}/api/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      // SSE 파싱
      const lines = chunk.split("\n");
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          yield JSON.parse(line.slice(6));
        }
      }
    }
  },
};
```

---

## 스트리밍 구현

### SSE (Server-Sent Events)

```tsx
// src/components/chat/message-input.tsx
"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useChatStore } from "@/stores/chat-store";

export function MessageInput() {
  const [input, setInput] = useState("");
  const { addMessage, updateStreamingMessage } = useChatStore();

  const handleSubmit = async () => {
    if (!input.trim()) return;

    // 사용자 메시지 추가
    addMessage({ role: "user", content: input });

    // AI 응답 스트리밍
    const stream = api.chatStream(input);
    let fullResponse = "";

    for await (const chunk of stream) {
      if (chunk.type === "token") {
        fullResponse += chunk.data;
        updateStreamingMessage(fullResponse);
      }
    }
  };

  return (
    <div className="flex gap-2">
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
        className="flex-1 p-2 border rounded"
      />
      <button onClick={handleSubmit}>Send</button>
    </div>
  );
}
```

---

## 보안

### 입력 검증

```typescript
// src/lib/security-validator.ts
const MAX_MESSAGE_LENGTH = 2000;
const INJECTION_PATTERNS = [
  "<script",
  "javascript:",
  "__import__",
  "eval(",
];

export function validateMessage(content: string): {
  isValid: boolean;
  error?: string;
} {
  if (content.length > MAX_MESSAGE_LENGTH) {
    return {
      isValid: false,
      error: `메시지는 ${MAX_MESSAGE_LENGTH}자 이내로 작성해주세요.`,
    };
  }

  const hasInjection = INJECTION_PATTERNS.some((pattern) =>
    content.toLowerCase().includes(pattern)
  );

  if (hasInjection) {
    return {
      isValid: false,
      error: "안전하지 않은 콘텐츠가 감지되었습니다.",
    };
  }

  return { isValid: true };
}
```

### XSS 방어

```tsx
// DOMPurify로 HTML 정화
import DOMPurify from "dompurify";

function renderMarkdown(content: string) {
  const sanitized = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: ["p", "br", "strong", "em", "code"],
    ALLOWED_ATTR: [],
  });
  return { __html: sanitized };
}
```

---

## 성능 최적화

### 이미지 최적화

```tsx
import Image from "next/image";

// Next.js Image 컴포넌트 사용
<Image
  src="/avatar.png"
  alt="Avatar"
  width={40}
  height={40}
  className="rounded-full"
/>
```

### 코드 분할

```tsx
// 동적 임포트
import dynamic from "next/dynamic";

const HeavyComponent = dynamic(
  () => import("@/components/heavy-component"),
  { loading: () => <div>Loading...</div> }
);
```

### 메모이제이션

```tsx
import { memo, useMemo, useCallback } from "react";

// 컴포넌트 메모이제이션
const MessageBubble = memo(function MessageBubble({ message }) {
  return <div>{message.content}</div>;
});

// 값 메모이제이션
const processedData = useMemo(() => {
  return data.map(item => expensiveOperation(item));
}, [data]);

// 백 메모이제이션
const handleClick = useCallback(() => {
  console.log("Clicked");
}, []);
```

---

## 배포

### Vercel (무료)

```bash
# Vercel CLI 설치
npm i -g vercel

# 배포
vercel

# 프로덕션 배포
vercel --prod
```

### 환경 변수

```bash
# .env.local
NEXT_PUBLIC_API_URL=https://api.yourapp.com
NEXT_PUBLIC_APP_NAME=AI Agent Chatbot
```

---

## 참고 자료

- [Next.js 공식 문서](https://nextjs.org/docs)
- [Zustand 문서](https://docs.pmnd.rs/zustand)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [shadcn/ui](https://ui.shadcn.com/)

---

*Frontend AGENTS.md*
*마지막 업데이트: 2026-02-15*
