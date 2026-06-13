import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  AgentListResponse,
  FileUploadResponse,
  DocumentListResponse,
  SessionResponse,
  SessionListResponse,
  MetricsSummary,
  MetricsPeriod,
} from '@/types';
import { API_BASE_URL, API_ENDPOINTS } from './constants';
import { tokenManager } from './token-manager';

/**
 * Extended error class for API errors with status codes
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Main fetch function with optional bearer-token support.
 * The product flow is guest-first, but existing stored tokens are still attached.
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  // Attach an optional bearer token if one exists.
  const token = tokenManager.getToken();

  // Prepare headers with Authorization
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Make the request
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Skip login redirects in guest mode.
  if (response.status === 401) {
    throw new ApiError('Unauthorized', 401);
  }

  // Handle other error responses
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new ApiError(
      error.detail || error.error || error.message || `HTTP ${response.status}`,
      response.status,
      error.detail
    );
  }

  return response.json();
}

/**
 * Fetch function for file uploads (multipart/form-data)
 * Doesn't set Content-Type to allow browser to set boundary
 */
async function fetchApiUpload<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const token = tokenManager.getToken();

  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Skip login redirects in guest mode.
  if (response.status === 401) {
    throw new ApiError('Unauthorized', 401);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new ApiError(
      error.detail || error.error || `HTTP ${response.status}`,
      response.status,
      error.detail
    );
  }

  return response.json();
}

export const api = {
  // Chat
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return fetchApi<ChatResponse>(API_ENDPOINTS.chat, {
      method: 'POST',
      body: JSON.stringify({ ...request, stream: false }),
    });
  },

  // Health
  async getHealth(): Promise<HealthResponse> {
    return fetchApi<HealthResponse>(API_ENDPOINTS.health);
  },

  // Agents
  async getAgents(): Promise<AgentListResponse> {
    return fetchApi<AgentListResponse>(API_ENDPOINTS.agents);
  },

  // File Upload (multipart/form-data)
  async uploadFile(
    file: File,
    sessionId: string,
    deviceId: string,
    metadata?: Record<string, string>
  ): Promise<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);
    formData.append('device_id', deviceId);
    formData.append('metadata', JSON.stringify(metadata || {}));

    return fetchApiUpload<FileUploadResponse>(`${API_ENDPOINTS.documents}/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  async getDocuments(deviceId: string, sessionId?: string): Promise<DocumentListResponse> {
    const params = new URLSearchParams({ device_id: deviceId });
    if (sessionId) {
      params.set('session_id', sessionId);
    }
    return fetchApi<DocumentListResponse>(`${API_ENDPOINTS.documents}?${params.toString()}`);
  },

  async deleteDocument(documentId: string, deviceId: string, sessionId?: string): Promise<void> {
    const params = new URLSearchParams({ device_id: deviceId });
    if (sessionId) {
      params.set('session_id', sessionId);
    }
    await fetchApi(`${API_ENDPOINTS.documents}/${documentId}?${params.toString()}`, { method: 'DELETE' });
  },

  // Session
  async createSession(
    title: string = 'New Chat',
    deviceId: string,
    sessionId?: string
  ): Promise<SessionResponse> {
    return fetchApi<SessionResponse>(API_ENDPOINTS.sessions, {
      method: 'POST',
      body: JSON.stringify({ title, device_id: deviceId, session_id: sessionId }),
    });
  },

  async listSessions(deviceId: string): Promise<SessionListResponse> {
    return fetchApi<SessionListResponse>(`${API_ENDPOINTS.sessions}?device_id=${encodeURIComponent(deviceId)}`);
  },

  async deleteSession(sessionId: string, deviceId: string): Promise<void> {
    await fetchApi(`${API_ENDPOINTS.sessionFull(sessionId)}?device_id=${encodeURIComponent(deviceId)}`, {
      method: 'DELETE',
    });
  },
  // Metrics
  async getMetricsSummary(period: MetricsPeriod = '24h'): Promise<MetricsSummary> {
    return fetchApi<MetricsSummary>(`${API_ENDPOINTS.metricsSummary}?period=${period}`);
  },
};
