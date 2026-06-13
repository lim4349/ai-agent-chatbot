// Backend API Types - Mirrors FastAPI schemas

export interface ChatRequest {
  message: string;
  session_id: string;
  device_id?: string;
  stream?: boolean;
}

export interface ChatResponse {
  message: string;
  session_id: string;
  agent_used: string;
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
  available_tools?: string[];
}

export interface AgentInfo {
  name: string;
  description: string;
  tools: string[];
}

export interface AgentListResponse {
  agents: AgentInfo[];
}

export interface FileUploadResponse {
  document_id: string;
  filename: string;
  file_type: string;
  chunks_created: number;
  total_tokens: number;
  upload_time: string;
  status: string;
  message: string;
  parse_summary?: DocumentParseSummary | null;
  warnings?: string[];
}

export interface DocumentParseSummary {
  page_count: number;
  table_count: number;
  element_count: number;
  parent_chunk_count: number;
  child_chunk_count: number;
  warnings: string[];
}

export interface DocumentInfo {
  id: string;
  filename: string;
  file_type: string;
  upload_time: string;
  chunk_count: number;
  total_tokens: number;
  parent_chunk_count?: number;
  child_chunk_count?: number;
  page_count?: number;
  table_count?: number;
  warnings?: string[];
}

export interface DocumentListResponse {
  documents: DocumentInfo[];
}

// Session API Types
export interface SessionResponse {
  id: string;
  user_id: string;
  title: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: SessionResponse[];
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
    results?: unknown[] | string;
    documentSources?: string[];
    sources?: string[];
    confidence?: string;
    status?: string;
  }>;
  status?: string;
  hasMemoryReference?: boolean;
  referencedTopics?: string[];
}

export interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  // Track if session exists in backend (Supabase)
  // true = local only, not yet synced to backend
  // false/undefined = exists in backend
  isLocalOnly?: boolean;
}

export type AgentType = 'assistant';

export interface SSECallbacks {
  onMetadata: (data: { session_id: string }) => void;
  onToken: (token: string) => void;
  onAgent: (agent: string) => void;
  onStatus: (message: string) => void;
  onTool: (tool: {
    tool?: string;
    name?: string;
    query?: string;
    results?: unknown[] | string;
    sources?: string[];
    confidence?: string;
    error?: string;
  }) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

// Re-export metrics types
export type {
  MetricsSummary,
  RequestMetricResponse,
  MetricsPeriod,
} from './metrics';
