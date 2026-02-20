# Frontend AGENTS.md

> Next.js 16 프론트엔드 개발 실전 가이드

---

## UI/UX 디자인 가이드라인

### 1. 컬러 선택

**AI에게 색깔을 직접 지정하지 마세요.** 대신 조화로운 팔레트를 사용합니다.

```
❌ 잘못된 예: "파란색 버튼", "#3B82F6 사용"
✅ 올바른 예: Coolors.co에서 생성한 팔레트 사용
```

**추천 도구**: [Coolors.co](https://coolors.co/)

### 2. 컬러 제한

**딱 2색만 사용하세요.** 메인 컬러 1개 + 서브 컬러 1개, 나머지는 흰색/검정/회색으로 채웁니다.

```
메인 컬러: 브랜드/강조용 (버튼, 링크, 하이라이트)
서브 컬러: 보조 강조용 (호버, 배지, 아이콘)
나머지: white, black, gray 계열
```

### 3. UI 라이브러리

**Next.js 프로젝트에서는 MUI 대신 shadcn/ui를 사용합니다.**

```
❌ MUI (Material UI)
   - 번들 사이즈가 큼
   - 커스터마이징이 복잡함
   - Next.js App Router와 호환성 이슈

✅ shadcn/ui
   - 가벼움 (사용하는 컴포넌트만)
   - Tailwind CSS 기반으로 커스터마이징 용이
   - Next.js와 완벽 호환
   - Radix UI 기반으로 접근성 우수
```

**컴포넌트 추가:**
```bash
npx shadcn add button dialog dropdown-menu
```

### 4. 디자인 가이드라인 예시

```css
/* globals.css */
:root {
  /* 메인 컬러 (Coolors에서 가져온 팔레트) */
  --primary: #2563EB;      /* 메인 블루 */
  --secondary: #10B981;    /* 서브 그린 */

  /* 중립색 */
  --background: #FFFFFF;
  --foreground: #0F172A;
  --muted: #F1F5F9;
  --muted-foreground: #64748B;
  --border: #E2E8F0;
}
```

---

## SSE 스트리밍 구현

**Server-Sent Events 실시간 스트리밍:**

```typescript
// src/lib/api.ts
export const api = {
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

**컴포넌트에서 사용:**
```tsx
"use client";

export function MessageInput() {
  const handleSubmit = async () => {
    const stream = api.chatStream(input);
    let fullResponse = "";

    for await (const chunk of stream) {
      if (chunk.type === "token") {
        fullResponse += chunk.data;
        updateStreamingMessage(fullResponse);
      }
    }
  };
}
```

---

## Zustand 스토어 설계

```typescript
// src/stores/chat-store.ts
import { create } from "zustand";

interface ChatState {
  // State
  messages: Message[];
  isStreaming: boolean;

  // Actions
  addMessage: (message: Message) => void;
  updateStreamingMessage: (content: string) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),

  updateStreamingMessage: (content) => set((state) => ({
    messages: state.messages.map((m, i) =>
      i === state.messages.length - 1
        ? { ...m, content }
        : m
    )
  })),
}));
```

---

## 성능 최적화

### 이미지 최적화

```tsx
import Image from "next/image";

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

// 콜백 메모이제이션
const handleClick = useCallback(() => {
  console.log("Clicked");
}, []);
```

---

## 코드 품질

```bash
# 린트
npm run lint

# 린트 자동 수정
npm run lint:fix

# 타입 체크
npx tsc --noEmit

# 빌드 테스트
npm run build
```

**주의사항:**
- `any` 타입 대신 `unknown` 사용 후 타입 가드 적용
- useEffect 내에서 직접 setState 호출 금지 → requestAnimationFrame 사용

---

## 개발 서버

```bash
# 개발 모드
npm run dev

# 프로덕션 모드
npm start
```

---

*Frontend AGENTS.md - 실전 개발 가이드*
