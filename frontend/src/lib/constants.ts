import type { AgentType } from '@/types';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  chat: '/api/v1/chat',
  chatStream: '/api/v1/chat/stream',
  health: '/api/v1/health',
  agents: '/api/v1/agents',
  documents: '/api/v1/documents',
  session: (id: string) => `/api/v1/sessions/${id}`,
  logs: '/api/v1/logs',
} as const;

export const AGENT_COLORS: Record<AgentType, { bg: string; text: string; label: string }> = {
  chat: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'Chat' },
  code: { bg: 'bg-purple-500/20', text: 'text-purple-400', label: 'Code' },
  rag: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'RAG' },
  web_search: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Web Search' },
  supervisor: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Router' },
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

// Authentication Constants
export const TOKEN_REFRESH_THRESHOLD = 5 * 60 * 1000; // 5 minutes before expiration
export const TOKEN_REFRESH_CHECK_INTERVAL = 60 * 1000; // Check every minute
export const SESSION_CHECK_INTERVAL = 5 * 60 * 1000; // Check session every 5 minutes

// Token Storage Keys
export const TOKEN_KEY = 'auth_token';
export const REFRESH_TOKEN_KEY = 'refresh_token';

// Auth Routes
export const AUTH_ROUTES = {
  login: '/login',
  register: '/register',
  logout: '/logout',
  profile: '/profile',
} as const;
