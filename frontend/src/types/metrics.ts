// Metrics API Types - Mirrors backend observability schemas

export interface MetricsSummary {
  period: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  blocked_requests: number;
  avg_duration_ms: number;
  total_tokens: number;
  agent_stats: AgentMetricItem[];
  start_time: string;
  end_time: string;
}

export interface AgentMetricItem {
  agent_name: string;
  date: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  blocked_requests: number;
  avg_duration_ms: number;
  total_tokens: number;
}

export interface AgentMetricsResponse {
  agent_name: string;
  date: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  blocked_requests: number;
  avg_duration_ms: number;
  total_tokens: number;
}

export interface RequestMetricResponse {
  session_id: string;
  agent_name: string;
  duration_ms: number;
  token_count: number;
  status: string;
  error_message: string | null;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export type MetricsPeriod = '24h' | '7d' | '30d';
