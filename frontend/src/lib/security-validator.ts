/**
 * Security Validator for Injection Pattern Detection
 * Provides real-time detection of potential security threats in user input
 */

import { MAX_MESSAGE_LENGTH, WARNING_THRESHOLD } from './constants';

export interface ValidationResult {
  valid: boolean;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  patterns?: string[];
  error?: string;
  warning?: string;
  injectionPattern?: string;
}

export interface SecurityConfig {
  maxMessageLength: number;
  enableRealTimeValidation: boolean;
  showInjectionWarnings: boolean;
}

// Enhanced injection patterns with severity levels and multilingual support
export const INJECTION_PATTERNS = {
  critical: [
    { pattern: /<script[^>]*>/i, name: 'Script tag', koName: '스크립트 태그' },
    { pattern: /javascript:/i, name: 'JavaScript protocol', koName: '자바스크립트 프로토콜' },
    { pattern: /on\w+\s*=/i, name: 'Event handler injection', koName: '이벤트 핸들러 인젝션' },
    { pattern: /<iframe[^>]*>/i, name: 'Iframe tag', koName: '아이프레임 태그' },
    { pattern: /<object[^>]*>/i, name: 'Object tag', koName: '오브젝트 태그' },
    { pattern: /<embed[^>]*>/i, name: 'Embed tag', koName: '임베드 태그' },
  ],
  error: [
    { pattern: /<[^>]*on\w+\s*=|<[^>]*style\s*=.*?expression/i, name: 'XSS attempt', koName: 'XSS 시도' },
    { pattern: /document\.(cookie|location|write)/i, name: 'Document manipulation', koName: '문서 조작 시도' },
    { pattern: /window\.(location|open)/i, name: 'Window manipulation', koName: '윈도우 조작 시도' },
  ],
  warning: [
    { pattern: /__import__\(/i, name: 'Python import injection', koName: 'Python import 인젝션' },
    { pattern: /eval\(/i, name: 'Eval function', koName: 'eval 함수' },
    { pattern: /exec\(/i, name: 'Exec function', koName: 'exec 함수' },
    { pattern: /\$\{.*?\}/i, name: 'Template injection', koName: '템플릿 인젝션' },
    { pattern: /<[^>]*>/i, name: 'HTML tag', koName: 'HTML 태그' },
    { pattern: /from\s+[\w.]+\s+import/i, name: 'Import statement', koName: 'import 문' },
    { pattern: /require\s*\(/i, name: 'Require function', koName: 'require 함수' },
  ],
  info: [
    {
      pattern: /ignore\s+(all\s+)?(instructions|above|previous)/i,
      name: 'Potential prompt injection',
      koName: '잠재적 프롬프트 인젝션'
    },
    {
      pattern: /repeat\s+(the\s+)?(above|previous|everything)/i,
      name: 'Data exfiltration attempt',
      koName: '데이터 유출 시도'
    },
    {
      pattern: /forget\s+(everything|all\s+instructions)/i,
      name: 'Context reset attempt',
      koName: '컨텍스트 리셋 시도'
    },
    {
      pattern: /disregard\s+(all\s+)?(previous|above)/i,
      name: 'Instruction override attempt',
      koName: '명령어 무시 시도'
    },
  ],
};

// Legacy patterns for backward compatibility
export const LEGACY_INJECTION_PATTERNS = [
  '<script',
  'javascript:',
  '__import__',
  'eval(',
  'exec(',
  '${',
  'ignore instructions',
];

/**
 * Validates user input for security threats with enhanced pattern detection
 * @param message - The user message to validate
 * @param config - Security configuration
 * @param locale - Current locale ('ko' or 'en')
 * @returns ValidationResult with severity and message
 */
export function validateSecurity(
  message: string,
  config: SecurityConfig,
  locale: 'ko' | 'en' = 'ko'
): ValidationResult {
  const results: ValidationResult = {
    valid: true,
    severity: 'info',
    message: '',
  };

  // Check message length
  if (message.length > config.maxMessageLength) {
    return {
      valid: false,
      severity: 'error',
      message: locale === 'ko'
        ? `메시지 길이가 제한을 초과했습니다 (${message.length}/${config.maxMessageLength})`
        : `Message length exceeds limit (${message.length}/${config.maxMessageLength})`,
      patterns: [`Length: ${message.length}/${config.maxMessageLength}`],
      error: locale === 'ko' ? 'chat.tooLong' : 'chat.tooLong',
    };
  }

  // Check critical patterns - block immediately
  for (const { pattern, name, koName } of INJECTION_PATTERNS.critical) {
    if (pattern.test(message)) {
      return {
        valid: false,
        severity: 'critical',
        message: locale === 'ko'
          ? `보안 위험: ${koName}(이)가 감지되었습니다. 이 메시지는 전송할 수 없습니다.`
          : `Security Risk: ${name} detected. This message cannot be sent.`,
        patterns: [locale === 'ko' ? koName : name],
        error: 'security.critical',
      };
    }
  }

  // Check error patterns - block immediately
  for (const { pattern, name, koName } of INJECTION_PATTERNS.error) {
    if (pattern.test(message)) {
      return {
        valid: false,
        severity: 'error',
        message: locale === 'ko'
          ? `보안 위험: ${koName}(이)가 감지되었습니다. 이 메시지는 전송할 수 없습니다.`
          : `Security Risk: ${name} detected. This message cannot be sent.`,
        patterns: [locale === 'ko' ? koName : name],
        error: 'security.error',
      };
    }
  }

  // Check warning patterns - warn but allow
  const warningPatterns: string[] = [];
  for (const { pattern, name, koName } of INJECTION_PATTERNS.warning) {
    if (pattern.test(message)) {
      warningPatterns.push(locale === 'ko' ? koName : name);
    }
  }

  if (warningPatterns.length > 0) {
    return {
      valid: true,
      severity: 'warning',
      message: locale === 'ko'
        ? `주의: ${warningPatterns.join(', ')}(이)가 포함되어 있습니다. 계속 진행하시겠습니까?`
        : `Warning: Contains ${warningPatterns.join(', ')}. Continue anyway?`,
      patterns: warningPatterns,
      warning: 'security.warning',
    };
  }

  // Check info patterns - informational
  for (const { pattern, name, koName } of INJECTION_PATTERNS.info) {
    if (pattern.test(message)) {
      return {
        valid: true,
        severity: 'info',
        message: locale === 'ko'
          ? `알림: ${koName} 패턴이 감지되었습니다.`
          : `Notice: ${name} pattern detected.`,
        patterns: [locale === 'ko' ? koName : name],
      };
    }
  }

  return results;
}

/**
 * Legacy validateMessage function for backward compatibility
 * @param message - The user message to validate
 * @returns ValidationResult with legacy structure
 */
export function validateMessage(message: string): ValidationResult {
  // Empty check
  if (message.trim().length === 0) {
    return {
      valid: false,
      error: 'chat.emptyMessage',
      severity: 'error',
      message: 'Message cannot be empty',
    };
  }

  // Length check
  if (message.length > MAX_MESSAGE_LENGTH) {
    return {
      valid: false,
      error: 'chat.tooLong',
      severity: 'error',
      message: 'Message exceeds maximum length',
    };
  }

  // Injection pattern warning (doesn't invalidate, just warns)
  const lowerMessage = message.toLowerCase();
  const foundPattern = LEGACY_INJECTION_PATTERNS.find((pattern) =>
    lowerMessage.includes(pattern.toLowerCase())
  );

  if (foundPattern) {
    return {
      valid: true,
      warning: 'chat.injectionWarning',
      injectionPattern: foundPattern,
      severity: 'warning',
      message: `Potential injection pattern: ${foundPattern}`,
      patterns: [foundPattern],
    };
  }

  return { valid: true, severity: 'info', message: '' };
}

/**
 * Sanitizes user input to remove potentially harmful content
 * @param message - The message to sanitize
 * @returns Sanitized message
 */
export function sanitizeInput(message: string): string {
  // Remove null bytes
  let sanitized = message.replace(/\x00/g, '');

  // Limit excessive repetitions (e.g., "aaaaa...")
  sanitized = sanitized.replace(/(.)\1{20,}/g, '$1'.repeat(5));

  // Remove excessive newlines
  sanitized = sanitized.replace(/\n{5,}/g, '\n\n\n');

  // Remove excessive spaces
  sanitized = sanitized.replace(/ {5,}/g, '   ');

  return sanitized;
}

/**
 * Checks if a message should be blocked based on severity
 * @param severity - The severity level
 * @returns true if message should be blocked
 */
export function shouldBlockMessage(severity: ValidationResult['severity']): boolean {
  return severity === 'critical' || severity === 'error';
}

/**
 * Gets the CSS class for a severity level
 * @param severity - The severity level
 * @returns CSS class string
 */
export function getSeverityClass(severity: ValidationResult['severity']): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-500 text-white border-red-600';
    case 'error':
      return 'bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700';
    case 'warning':
      return 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-700';
    case 'info':
      return 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-300';
  }
}

/**
 * Gets the icon component name for a severity level
 * @param severity - The severity level
 * @returns Icon component name from lucide-react
 */
export function getSeverityIcon(severity: ValidationResult['severity']): string {
  switch (severity) {
    case 'critical':
      return 'ShieldAlert';
    case 'error':
      return 'XCircle';
    case 'warning':
      return 'AlertTriangle';
    case 'info':
      return 'Info';
    default:
      return 'Info';
  }
}

export function getCharacterCountStatus(length: number): {
  status: 'normal' | 'warning' | 'error';
  percentage: number;
} {
  const percentage = (length / MAX_MESSAGE_LENGTH) * 100;

  if (length > MAX_MESSAGE_LENGTH) {
    return { status: 'error', percentage: 100 };
  }

  if (length >= WARNING_THRESHOLD) {
    return { status: 'warning', percentage };
  }

  return { status: 'normal', percentage };
}

export function truncateToMaxLength(message: string): string {
  return message.slice(0, MAX_MESSAGE_LENGTH);
}
