// Backend API Types - Mirrors FastAPI schemas

export interface ChatRequest {
  message: string;
  session_id: string;
  stream?: boolean;
}

export interface ChatResponse {
  message: string;
  session_id: string;
  agent_used: string;
  route_reasoning: string | null;
  tool_results: Record<string, unknown>[];
  created_at: string;
  tools_used?: Array<{
    name: string;
    query?: string;
    results_count?: number;
    sources?: string[];
  }>;
  memory_referenced?: boolean;
  referenced_topics?: string[];
}

export interface HealthResponse {
  status: string;
  llm_provider: string;
  llm_model: string;
  memory_backend: string;
  available_agents: string[];
}

export interface AgentInfo {
  name: string;
  description: string;
  tools: string[];
}

export interface AgentListResponse {
  agents: AgentInfo[];
}

export interface DocumentUploadRequest {
  content: string;
  metadata?: Record<string, unknown>;
}

export interface DocumentUploadResponse {
  status: string;
  message: string;
}

export interface FileUploadRequest {
  file: File;
  metadata?: Record<string, string>;
}

export interface FileUploadResponse {
  document_id: string;
  filename: string;
  file_type: string;
  chunks_created: number;
  total_tokens: number;
  status: string;
  message: string;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  file_type: string;
  upload_time: string;
  chunk_count: number;
  total_tokens: number;
}

export interface DocumentListResponse {
  documents: DocumentInfo[];
}

// Frontend-only types

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  agent?: string;
  createdAt: Date;
  tools?: Array<{
    name: string;
    query?: string;
    results?: unknown[];
    documentSources?: string[];
  }>;
  hasMemoryReference?: boolean;
  referencedTopics?: string[];
}

export interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
}

export type AgentType = 'chat' | 'code' | 'rag' | 'web_search' | 'supervisor';

export interface SSECallbacks {
  onMetadata: (data: { session_id: string }) => void;
  onToken: (token: string) => void;
  onAgent: (agent: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

// Authentication Types

export interface User {
  id: string;
  email: string;
  username?: string;
  full_name?: string;
  avatar_url?: string;
  created_at?: string;
  updated_at?: string;
  is_active?: boolean;
  role?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  remember?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  remember?: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  username?: string;
  full_name?: string;
}

export interface RegisterResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
}

export interface AuthError {
  error: string;
  detail?: string;
  status?: number;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}
