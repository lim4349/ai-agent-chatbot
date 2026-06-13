import type { AgentType } from '@/types';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export const API_ENDPOINTS = {
  chat: '/api/v1/chat',
  chatStream: '/api/v1/chat/stream',
  health: '/api/v1/health',
  agents: '/api/v1/agents',
  documents: '/api/v1/documents',
  sessions: '/api/v1/sessions',
  session: (id: string) => `/api/v1/sessions/${id}`,
  sessionFull: (id: string) => `/api/v1/sessions/${id}/full`,
  logs: '/api/v1/logs',
  metricsSummary: '/api/v1/metrics/summary',
} as const;

export const AGENT_COLORS: Record<AgentType, { bg: string; text: string; label: string }> = {
  assistant: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Assistant' },
};

export const MAX_MESSAGE_LENGTH = 2000;
export const WARNING_THRESHOLD = 1800;

// Dangerous injection patterns to warn users about
export const INJECTION_PATTERNS = [
  '<script',
  'javascript:',
  '__import__',
  'eval(',
  'exec(',
  '${',
  'ignore instructions',
];
export const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds
