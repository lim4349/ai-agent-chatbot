export type ErrorType = 'network' | 'timeout' | 'server' | 'unknown';

export interface ChatError {
  message: string;
  type: ErrorType;
  retryable: boolean;
  originalError?: string;
}

export function classifyChatError(error: string): ChatError {
  const lowerError = error.toLowerCase();

  if (
    lowerError.includes('network') ||
    lowerError.includes('fetch') ||
    lowerError.includes('connection') ||
    lowerError.includes('econnrefused') ||
    lowerError.includes('name or service not known') ||
    lowerError.includes('dns')
  ) {
    return {
      message: '네트워크 연결이 불안정합니다. 인터넷 연결을 확인해주세요.',
      type: 'network',
      retryable: true,
      originalError: error,
    };
  }

  if (lowerError.includes('timeout') || lowerError.includes('timed out')) {
    return {
      message: '요청 시간이 초과되었습니다. 다시 시도해주세요.',
      type: 'timeout',
      retryable: true,
      originalError: error,
    };
  }

  if (
    lowerError.includes('500') ||
    lowerError.includes('502') ||
    lowerError.includes('503') ||
    lowerError.includes('429') ||
    lowerError.includes('server error')
  ) {
    return {
      message: '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
      type: 'server',
      retryable: true,
      originalError: error,
    };
  }

  return {
    message: '오류가 발생했습니다. 다시 시도해주세요.',
    type: 'unknown',
    retryable: true,
    originalError: error,
  };
}
