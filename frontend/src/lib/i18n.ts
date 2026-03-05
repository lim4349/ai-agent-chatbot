import { useCallback } from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { MAX_MESSAGE_LENGTH } from './constants';

export type Locale = 'ko' | 'en';

const translations = {
  ko: {
    // Header
    'header.title': 'AI 에이전트 챗봇',
    'header.dashboard': '대시보드',

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
    'doc.dropHere': '파일을 여기에 놓으세요',
    'doc.dragDrop': '파일을 끌어다 놓으세요',
    'doc.processing': '처리 중...',
    'doc.processWait': '파일을 처리하는 동안 기다려주세요',
    'doc.clickSelect': '또는 클릭하여 파일 선택',
    'doc.supported': '지원 형식',
    'doc.maxSize': '최대 파일 크기',
    'doc.invalid': '유효하지 않음',
    'doc.tooLarge': '너무 큼',
    'doc.largeFile': '큰 파일',
    'doc.error': '오류',
    'doc.errors': '개 오류',
    'doc.warning': '경고',
    'doc.warnings': '개 경고',
    'doc.uploadAnyway': '계속 업로드',
    'doc.validating': '검증 중...',
    'doc.percentOfLimit': '제한의',
    'doc.fileTypeNotSupported': '지원하지 않는 파일 형식',
    'doc.removeFile': '파일 제거',

    // Health
    'health.connected': '연결됨',
    'health.disconnected': '연결 끊김',
    'health.checking': '확인 중...',
    'health.dailyQuota': '일일 할당량',
    'health.requestsToday': '오늘 요청',
    'health.remaining': '남음',
    'health.perMinute': '분당 호출',
    'health.perHour': '시간당 호출',
    'health.dailyRequests': '일일 호출',
    'health.used': '사용',
    'health.resetsIn': (s: number) => {
      if (s <= 0) return '곧 초기화';
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      if (h > 0) return `${h}시간 ${m}분 후`;
      if (m > 0) return `${m}분 ${sec}초 후`;
      return `${sec}초 후`;
    },
    'health.unlimited': '무제한',

    // Agent labels
    'agent.chat': '대화',
    'agent.code': '코드',
    'agent.rag': 'RAG',
    'agent.web_search': '웹 검색',
    'agent.supervisor': '라우터',
    'agent.report': '보고서',
    'agent.additionalAgents': '추가 에이전트',

    // Security
    'security.critical': '보안 위험 감지',
    'security.error': '보안 오류',
    'security.warning': '보안 경고',
    'security.info': '보안 정보',
    'security.blocked': '이 메시지는 전송할 수 없습니다',
    'security.proceed': '계속 진행하시겠습니까?',
    'security.dismiss': '닫기',
    'security.patterns': '감지된 패턴:',

    // Dashboard
    'dashboard.title': '대시보드',
    'dashboard.description': '시스템 메트릭 및 성능 인사이트',
    'dashboard.totalRequests': '총 요청',
    'dashboard.successRate': '성공률',
    'dashboard.avgDuration': '평균 응답시간',
    'dashboard.totalTokens': '총 토큰',
    'dashboard.requestsByAgent': '에이전트별 요청',
    'dashboard.requestsByAgentDescription': '에이전트 간 요청 분포',
    'dashboard.requestStatus': '요청 상태',
    'dashboard.requestStatusDescription': '성공, 실패 및 차단된 요청',
    'dashboard.tokensByAgent': '에이전트별 토큰',
    'dashboard.tokensByAgentDescription': '에이전트별 처리된 총 토큰',
    'dashboard.avgDurationByAgent': '에이전트별 평균 응답시간',
    'dashboard.avgDurationByAgentDescription': '에이전트별 평균 응답 시간 (ms)',
    'dashboard.agentStatistics': '에이전트 통계',
    'dashboard.agentStatisticsDescription': '각 에이전트의 상세 메트릭',
    'dashboard.period': '기간',
    'dashboard.of': '의',
    'dashboard.loading': '메트릭 로딩 중...',
    'dashboard.noData': '데이터 없음',
    'dashboard.noAgentStats': '이 기간에 대한 에이전트 통계가 없습니다',
    'dashboard.success': '성공',
    'dashboard.failed': '실패',
    'dashboard.blocked': '차단됨',
    'dashboard.agent': '에이전트',
    'dashboard.total': '총',
    'dashboard.tokens': '토큰',
    'dashboard.tokensProcessed': '처리된 토큰',
    'dashboard.avgResponseTime': '평균 응답 시간',
    'dashboard.retry': '재시도',
    'dashboard.error': '오류',
  },
  en: {
    'header.title': 'AI Agent Chatbot',
    'header.dashboard': 'Dashboard',

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
    'doc.dropHere': 'Drop your file here',
    'doc.dragDrop': 'Drag & drop a file here',
    'doc.processing': 'Processing...',
    'doc.processWait': 'Please wait while we process your file',
    'doc.clickSelect': 'or click to select a file',
    'doc.supported': 'Supported',
    'doc.maxSize': 'Maximum file size',
    'doc.invalid': 'Invalid',
    'doc.tooLarge': 'Too large',
    'doc.largeFile': 'Large file',
    'doc.error': 'Error',
    'doc.errors': 'Errors',
    'doc.warning': 'Warning',
    'doc.warnings': 'Warnings',
    'doc.uploadAnyway': 'Upload anyway',
    'doc.validating': 'Validating...',
    'doc.percentOfLimit': 'of limit',
    'doc.fileTypeNotSupported': 'File type not supported',
    'doc.removeFile': 'Remove file',

    'health.connected': 'Connected',
    'health.disconnected': 'Disconnected',
    'health.checking': 'Checking...',
    'health.dailyQuota': 'Daily Quota',
    'health.requestsToday': 'Today\'s Requests',
    'health.remaining': 'Remaining',
    'health.perMinute': 'Per Minute',
    'health.perHour': 'Per Hour',
    'health.dailyRequests': 'Daily Calls',
    'health.used': 'Used',
    'health.resetsIn': (s: number) => {
      if (s <= 0) return 'resetting soon';
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      if (h > 0) return `in ${h}h ${m}m`;
      if (m > 0) return `in ${m}m ${sec}s`;
      return `in ${sec}s`;
    },
    'health.unlimited': 'Unlimited',

    'agent.chat': 'Chat',
    'agent.code': 'Code',
    'agent.rag': 'RAG',
    'agent.web_search': 'Web Search',
    'agent.supervisor': 'Router',
    'agent.report': 'Report',
    'agent.additionalAgents': 'Additional agents',

    // Security
    'security.critical': 'Security Risk Detected',
    'security.error': 'Security Error',
    'security.warning': 'Security Warning',
    'security.info': 'Security Information',
    'security.blocked': 'This message cannot be sent',
    'security.proceed': 'Continue anyway?',
    'security.dismiss': 'Dismiss',
    'security.patterns': 'Patterns detected:',

    // Dashboard
    'dashboard.title': 'Observability Dashboard',
    'dashboard.description': 'System metrics and performance insights',
    'dashboard.totalRequests': 'Total Requests',
    'dashboard.successRate': 'Success Rate',
    'dashboard.avgDuration': 'Avg Duration',
    'dashboard.totalTokens': 'Total Tokens',
    'dashboard.requestsByAgent': 'Requests by Agent',
    'dashboard.requestsByAgentDescription': 'Distribution of requests across agents',
    'dashboard.requestStatus': 'Request Status',
    'dashboard.requestStatusDescription': 'Success, failed, and blocked requests',
    'dashboard.tokensByAgent': 'Tokens by Agent',
    'dashboard.tokensByAgentDescription': 'Total tokens processed per agent',
    'dashboard.avgDurationByAgent': 'Avg Duration by Agent',
    'dashboard.avgDurationByAgentDescription': 'Average response time per agent (ms)',
    'dashboard.agentStatistics': 'Agent Statistics',
    'dashboard.agentStatisticsDescription': 'Detailed metrics for each agent',
    'dashboard.period': 'Period',
    'dashboard.of': 'of',
    'dashboard.loading': 'Loading metrics...',
    'dashboard.noData': 'No data available',
    'dashboard.noAgentStats': 'No agent statistics available for this period',
    'dashboard.success': 'Success',
    'dashboard.failed': 'Failed',
    'dashboard.blocked': 'Blocked',
    'dashboard.agent': 'Agent',
    'dashboard.total': 'Total',
    'dashboard.tokens': 'Tokens',
    'dashboard.tokensProcessed': 'Tokens processed',
    'dashboard.avgResponseTime': 'Average response time',
    'dashboard.retry': 'Retry',
    'dashboard.error': 'Error',
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
