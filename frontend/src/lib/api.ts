import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  AgentListResponse,
  DocumentUploadRequest,
  DocumentUploadResponse,
  FileUploadResponse,
  DocumentListResponse,
  SessionResponse,
  SessionListResponse,
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
 * Main fetch function with JWT token support and automatic refresh
 * Handles authentication, token expiration, and retry logic
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
  isRetry: boolean = false
): Promise<T> {
  // Get current token
  const token = tokenManager.getToken();

  // Prepare headers with Authorization
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  };

  // Add Authorization header if token exists
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Make the request
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized - skip login redirect in guest mode
  if (response.status === 401) {
    throw new ApiError('Unauthorized', 401);
  }

  // Handle other error responses
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new ApiError(
      error.error || error.message || `HTTP ${response.status}`,
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
  options?: RequestInit,
  isRetry: boolean = false
): Promise<T> {
  const token = tokenManager.getToken();

  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> || {}),
  };

  // Add Authorization header if token exists
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized - skip login redirect in guest mode
  if (response.status === 401) {
    throw new ApiError('Unauthorized', 401);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new ApiError(
      error.error || `HTTP ${response.status}`,
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

  // Documents
  async uploadDocument(request: DocumentUploadRequest): Promise<DocumentUploadResponse> {
    return fetchApi<DocumentUploadResponse>(API_ENDPOINTS.documents, {
      method: 'POST',
      body: JSON.stringify(request),
    });
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

  async getDocuments(deviceId: string): Promise<DocumentListResponse> {
    return fetchApi<DocumentListResponse>(`${API_ENDPOINTS.documents}?device_id=${encodeURIComponent(deviceId)}`);
  },

  async deleteDocument(documentId: string, deviceId: string): Promise<void> {
    await fetchApi(`${API_ENDPOINTS.documents}/${documentId}?device_id=${encodeURIComponent(deviceId)}`, { method: 'DELETE' });
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

  async clearSession(sessionId: string): Promise<void> {
    await fetchApi(API_ENDPOINTS.session(sessionId), {
      method: 'DELETE',
    });
  },
};
