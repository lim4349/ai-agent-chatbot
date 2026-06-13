import { useCallback } from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { MAX_MESSAGE_LENGTH } from './constants';

export type Locale = 'ko' | 'en';

const translations = {
  ko: {
    // Header
    'header.title': 'AI 에이전트 챗봇',
    'header.shortTitle': 'AI 챗봇',
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
    'chat.senderUser': '나',
    'chat.senderAssistant': '어시스턴트',

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
    'doc.unknownFile': '알 수 없는 파일',
    'doc.noActiveSession': '활성 대화가 없습니다. 먼저 새 대화를 만들어주세요.',
    'doc.uploadSuccess': (name: string) => `${name} 업로드 완료`,
    'doc.uploadFailed': '업로드 실패',
    'doc.listTitle': '업로드된 문서',
    'doc.listDescription': '현재 대화에서 사용할 수 있는 RAG 문서',
    'doc.loading': '문서 목록을 불러오는 중...',
    'doc.noDocumentsTitle': '아직 문서가 없습니다',
    'doc.noDocumentsDescription': '문서를 업로드하면 질문에 답변할 때 근거로 사용됩니다.',
    'doc.deleteConfirm': (name: string) => `"${name}" 문서를 삭제할까요?`,
    'doc.deleting': '삭제 중...',
    'doc.chunks': '청크',
    'doc.searchChunks': '검색 청크',
    'doc.tokens': '토큰',
    'doc.pages': (count: number) => `${count}페이지`,
    'doc.tables': (count: number) => `표 ${count}개`,
    'doc.parseWarnings': (count: number) => `파싱 경고 ${count}개`,
    'doc.fetchError': '문서 목록을 불러오지 못했습니다',

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
    'health.provider': '제공자',
    'health.model': '모델',
    'health.memory': '메모리',
    'health.agents': '에이전트',
    'health.tools': '도구',
    'health.backendUnavailable': '백엔드를 사용할 수 없습니다',
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
    'agent.assistant': '어시스턴트',
    'agent.assistantDescription': '대화, 메모리, 근거 수집을 통합 처리',

    // Tool labels
    'tool.web_search': '웹 검색',
    'tool.retriever': '문서 검색',
    'tool.unknown': '도구',
    'tool.showDetails': '도구 사용 내역 보기',
    'tool.hideDetails': '도구 사용 내역 숨기기',
    'tool.used': (count: number) => `${count}개 도구 사용`,
    'tool.results': (count: number) => `${count}개 결과`,
    'tool.confidence': '신뢰도',
    'tool.sources': '출처',
    'tool.evidence': '근거 상세',
    'tool.page': (page: number) => `${page}페이지`,
    'tool.pages': (start: number, end: number) => `${start}-${end}페이지`,
    'tool.heading': '섹션',
    'tool.score': '점수',
    'tool.lowConfidence': '낮은 신뢰도',
    'tool.unknownSource': '알 수 없는 출처',
    'tool.error': '오류',

    // Evidence confidence labels
    'confidence.high': '높음',
    'confidence.medium': '보통',
    'confidence.low': '낮음',
    'confidence.none': '근거 없음',
    'confidence.error': '오류',

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
    'dashboard.title': '어시스턴트 대시보드',
    'dashboard.description': '단일 Assistant 워크플로우의 처리량, 안정성, 근거 사용 현황',
    'dashboard.totalRequests': '총 요청',
    'dashboard.successRate': '성공률',
    'dashboard.avgDuration': '평균 응답시간',
    'dashboard.totalTokens': '총 토큰',
    'dashboard.requestStatus': '요청 상태',
    'dashboard.requestStatusDescription': '성공, 실패 및 차단된 요청',
    'dashboard.evidenceOverview': '근거 사용 현황',
    'dashboard.evidenceOverviewDescription': '근거 기반 응답과 일반 응답 분포',
    'dashboard.confidenceDistribution': '근거 신뢰도 분포',
    'dashboard.confidenceDistributionDescription': '수집된 근거의 신뢰도 요약',
    'dashboard.assistantSummary': '어시스턴트 처리 요약',
    'dashboard.assistantSummaryDescription': '단일 Assistant 워크플로우의 핵심 처리 지표',
    'dashboard.period': '기간',
    'dashboard.of': '의',
    'dashboard.loading': '메트릭 로딩 중...',
    'dashboard.noData': '데이터 없음',
    'dashboard.noToolUsage': '이 기간에는 도구 호출이 없습니다',
    'dashboard.noConfidenceData': '이 기간에는 신뢰도 데이터가 없습니다',
    'dashboard.success': '성공',
    'dashboard.failed': '실패',
    'dashboard.blocked': '차단됨',
    'dashboard.tokensProcessed': '처리된 토큰',
    'dashboard.avgResponseTime': '평균 응답 시간',
    'dashboard.evidenceRate': '근거 사용률',
    'dashboard.evidenceRateDescription': '리서치 근거를 수집한 응답 비율',
    'dashboard.evidenceTurns': '근거 사용 응답',
    'dashboard.evidenceTurnsDescription': '도구 또는 문서 근거를 사용한 응답',
    'dashboard.noEvidenceTurns': '근거 미사용 응답',
    'dashboard.noEvidenceTurnsDescription': '외부 근거 없이 답변한 응답',
    'dashboard.evidenceToolUsage': '근거 도구 사용량',
    'dashboard.evidenceToolUsageDescription': '어시스턴트 응답에서 기록된 도구 호출',
    'dashboard.requests': '요청',
    'dashboard.responses': '응답',
    'dashboard.calls': '호출',
    'dashboard.retry': '재시도',
    'dashboard.error': '오류',
    'dashboard.metricsUnavailable': '메트릭을 사용할 수 없습니다',
    'dashboard.metricsUnavailableDescription': '운영 메트릭 저장소 또는 백엔드 연결 상태를 확인해주세요.',
    'dashboard.lastUpdated': (time: string) => `마지막 갱신: ${time}`,
    'dashboard.lowSample': '표본 수가 적어 추세 판단이 제한적입니다',
  },
  en: {
    'header.title': 'AI Agent Chatbot',
    'header.shortTitle': 'AI Chat',
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
    'chat.senderUser': 'You',
    'chat.senderAssistant': 'Assistant',

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
    'doc.unknownFile': 'Unknown file',
    'doc.noActiveSession': 'No active session. Please create a session first.',
    'doc.uploadSuccess': (name: string) => `${name} uploaded successfully`,
    'doc.uploadFailed': 'Upload failed',
    'doc.listTitle': 'Uploaded documents',
    'doc.listDescription': 'RAG documents available in this conversation',
    'doc.loading': 'Loading documents...',
    'doc.noDocumentsTitle': 'No documents yet',
    'doc.noDocumentsDescription': 'Upload documents to ground answers with your knowledge base.',
    'doc.deleteConfirm': (name: string) => `Delete "${name}"?`,
    'doc.deleting': 'Deleting...',
    'doc.chunks': 'chunks',
    'doc.searchChunks': 'search chunks',
    'doc.tokens': 'tokens',
    'doc.pages': (count: number) => `${count} page${count === 1 ? '' : 's'}`,
    'doc.tables': (count: number) => `${count} table${count === 1 ? '' : 's'}`,
    'doc.parseWarnings': (count: number) => `${count} parse warning${count === 1 ? '' : 's'}`,
    'doc.fetchError': 'Failed to load documents',

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
    'health.provider': 'Provider',
    'health.model': 'Model',
    'health.memory': 'Memory',
    'health.agents': 'Agents',
    'health.tools': 'Tools',
    'health.backendUnavailable': 'Backend unavailable',
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

    'agent.assistant': 'Assistant',
    'agent.assistantDescription': 'Handles conversation, memory, and evidence collection',

    // Tool labels
    'tool.web_search': 'Web search',
    'tool.retriever': 'Document retrieval',
    'tool.unknown': 'Tool',
    'tool.showDetails': 'Show tool details',
    'tool.hideDetails': 'Hide tool details',
    'tool.used': (count: number) => `${count} tool${count === 1 ? '' : 's'} used`,
    'tool.results': (count: number) => `${count} result${count === 1 ? '' : 's'}`,
    'tool.confidence': 'Confidence',
    'tool.sources': 'Sources',
    'tool.evidence': 'Evidence details',
    'tool.page': (page: number) => `Page ${page}`,
    'tool.pages': (start: number, end: number) => `Pages ${start}-${end}`,
    'tool.heading': 'Section',
    'tool.score': 'Score',
    'tool.lowConfidence': 'Low confidence',
    'tool.unknownSource': 'Unknown source',
    'tool.error': 'Error',

    // Evidence confidence labels
    'confidence.high': 'High',
    'confidence.medium': 'Medium',
    'confidence.low': 'Low',
    'confidence.none': 'No evidence',
    'confidence.error': 'Error',

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
    'dashboard.title': 'Assistant Dashboard',
    'dashboard.description': 'Throughput, reliability, and evidence usage for the single Assistant workflow',
    'dashboard.totalRequests': 'Total Requests',
    'dashboard.successRate': 'Success Rate',
    'dashboard.avgDuration': 'Avg Duration',
    'dashboard.totalTokens': 'Total Tokens',
    'dashboard.requestStatus': 'Request Status',
    'dashboard.requestStatusDescription': 'Success, failed, and blocked requests',
    'dashboard.evidenceOverview': 'Evidence Overview',
    'dashboard.evidenceOverviewDescription': 'Evidence-backed and direct response distribution',
    'dashboard.confidenceDistribution': 'Evidence Confidence',
    'dashboard.confidenceDistributionDescription': 'Confidence summary for collected evidence',
    'dashboard.assistantSummary': 'Assistant Summary',
    'dashboard.assistantSummaryDescription': 'Core metrics for the single Assistant workflow',
    'dashboard.period': 'Period',
    'dashboard.of': 'of',
    'dashboard.loading': 'Loading metrics...',
    'dashboard.noData': 'No data available',
    'dashboard.noToolUsage': 'No tool calls recorded for this period',
    'dashboard.noConfidenceData': 'No confidence data for this period',
    'dashboard.success': 'Success',
    'dashboard.failed': 'Failed',
    'dashboard.blocked': 'Blocked',
    'dashboard.tokensProcessed': 'Tokens processed',
    'dashboard.avgResponseTime': 'Average response time',
    'dashboard.evidenceRate': 'Evidence Rate',
    'dashboard.evidenceRateDescription': 'Share of turns with collected research evidence',
    'dashboard.evidenceTurns': 'Evidence Turns',
    'dashboard.evidenceTurnsDescription': 'Responses grounded by tools or documents',
    'dashboard.noEvidenceTurns': 'No Evidence Turns',
    'dashboard.noEvidenceTurnsDescription': 'Responses answered without external evidence',
    'dashboard.evidenceToolUsage': 'Evidence Tool Usage',
    'dashboard.evidenceToolUsageDescription': 'Tool calls recorded from assistant turns',
    'dashboard.requests': 'Requests',
    'dashboard.responses': 'Responses',
    'dashboard.calls': 'Calls',
    'dashboard.retry': 'Retry',
    'dashboard.error': 'Error',
    'dashboard.metricsUnavailable': 'Metrics unavailable',
    'dashboard.metricsUnavailableDescription': 'Check the metrics store or backend connection.',
    'dashboard.lastUpdated': (time: string) => `Last updated: ${time}`,
    'dashboard.lowSample': 'Sample size is low, so trends are limited',
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
