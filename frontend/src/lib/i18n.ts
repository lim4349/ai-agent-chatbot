import { useCallback } from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { MAX_MESSAGE_LENGTH } from './constants';

export type Locale = 'ko' | 'en';

const translations = {
  ko: {
    // Header
    'header.title': 'AI 에이전트 챗봇',

    // Sidebar
    'sidebar.title': '대화 목록',
    'sidebar.newChat': '새 대화',
    'sidebar.empty': '대화가 없습니다',
    'sidebar.count': (n: number) => `${n}개의 대화`,

    // Chat
    'chat.placeholder': '대화를 시작하세요',
    'chat.placeholderSub': 'AI 어시스턴트와 대화를 시작해보세요',
    'chat.inputPlaceholder': '메시지를 입력하세요...',
    'chat.inputHint': 'Enter로 전송, Shift+Enter로 줄바꿈',
    'chat.tooLong': `메시지는 ${MAX_MESSAGE_LENGTH}자 이내로 작성해주세요.`,
    'chat.emptyMessage': '메시지를 입력해주세요.',
    'chat.injectionWarning': (pattern: string) => `주의: 안전하지 않은 콘텐츠가 감지되었습니다 (${pattern})`,
    'chat.copied': '복사됨',
    'chat.copy': '복사',
    'chat.copyCode': '코드 복사',
    'chat.copyMessage': '메시지 복사',

    // Document
    'doc.upload': '문서 업로드',
    'doc.uploadTitle': '문서 업로드',
    'doc.uploadDescription': 'RAG 지식 베이스에 문서를 추가하세요. AI가 이 정보를 바탕으로 질문에 답변합니다.',
    'doc.uploadFile': '파일 업로드',
    'doc.pasteText': '텍스트 입력',
    'doc.cancel': '취소',
    'doc.uploadButton': '업로드',
    'doc.uploading': '업로드 중...',
    'doc.placeholder': '문서 내용을 여기에 붙여넣으세요...',

    // Health
    'health.connected': '연결됨',
    'health.disconnected': '연결 끊김',
    'health.checking': '확인 중...',

    // Agent labels
    'agent.chat': '대화',
    'agent.code': '코드',
    'agent.rag': 'RAG',
    'agent.web_search': '웹 검색',
    'agent.supervisor': '라우터',

    // Security
    'security.critical': '보안 위험 감지',
    'security.error': '보안 오류',
    'security.warning': '보안 경고',
    'security.info': '보안 정보',
    'security.blocked': '이 메시지는 전송할 수 없습니다',
    'security.proceed': '계속 진행하시겠습니까?',
    'security.dismiss': '닫기',
    'security.patterns': '감지된 패턴:',
  },
  en: {
    'header.title': 'AI Agent Chatbot',

    'sidebar.title': 'Chats',
    'sidebar.newChat': 'New Chat',
    'sidebar.empty': 'No conversations yet',
    'sidebar.count': (n: number) => `${n} conversation${n !== 1 ? 's' : ''}`,

    'chat.placeholder': 'Start a conversation',
    'chat.placeholderSub': 'Send a message to begin chatting with the AI assistant',
    'chat.inputPlaceholder': 'Type a message...',
    'chat.inputHint': 'Press Enter to send, Shift+Enter for new line',
    'chat.tooLong': `Message must be within ${MAX_MESSAGE_LENGTH} characters.`,
    'chat.emptyMessage': 'Please enter a message.',
    'chat.injectionWarning': (pattern: string) => `Warning: Unsafe content detected (${pattern})`,
    'chat.copied': 'Copied',
    'chat.copy': 'Copy',
    'chat.copyCode': 'Copy code',
    'chat.copyMessage': 'Copy message',

    'doc.upload': 'Upload Document',
    'doc.uploadTitle': 'Upload Document',
    'doc.uploadDescription': 'Add documents to the RAG knowledge base. The AI will use this information to answer questions.',
    'doc.uploadFile': 'Upload File',
    'doc.pasteText': 'Paste Text',
    'doc.cancel': 'Cancel',
    'doc.uploadButton': 'Upload',
    'doc.uploading': 'Uploading...',
    'doc.placeholder': 'Paste your document content here...',

    'health.connected': 'Connected',
    'health.disconnected': 'Disconnected',
    'health.checking': 'Checking...',

    'agent.chat': 'Chat',
    'agent.code': 'Code',
    'agent.rag': 'RAG',
    'agent.web_search': 'Web Search',
    'agent.supervisor': 'Router',

    // Security
    'security.critical': 'Security Risk Detected',
    'security.error': 'Security Error',
    'security.warning': 'Security Warning',
    'security.info': 'Security Information',
    'security.blocked': 'This message cannot be sent',
    'security.proceed': 'Continue anyway?',
    'security.dismiss': 'Dismiss',
    'security.patterns': 'Patterns detected:',
  },
} as const;

export type TranslationKey = keyof typeof translations.en;

interface LocaleStore {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
}

export const useLocaleStore = create<LocaleStore>()(
  persist(
    (set) => ({
      locale: 'ko',
      setLocale: (locale) => set({ locale }),
      toggleLocale: () =>
        set((state) => ({ locale: state.locale === 'ko' ? 'en' : 'ko' })),
    }),
    {
      name: 'locale-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ locale: state.locale }),
    }
  )
);

/**
 * Hook that subscribes to locale changes and returns a translation function.
 * Components using this hook will re-render when locale changes.
 */
export function useTranslation() {
  const locale = useLocaleStore((state) => state.locale);
  const toggleLocale = useLocaleStore((state) => state.toggleLocale);

  const t = useCallback(
    (key: TranslationKey, ...args: unknown[]): string => {
      const value = translations[locale][key];
      if (typeof value === 'function') {
        return (value as (...a: unknown[]) => string)(...args);
      }
      return value as string;
    },
    [locale]
  );

  return { locale, t, toggleLocale };
}
