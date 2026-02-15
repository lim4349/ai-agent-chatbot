import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  AgentListResponse,
  DocumentUploadRequest,
  DocumentUploadResponse,
  FileUploadResponse,
  DocumentListResponse,
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

  // Handle 401 Unauthorized - token expired or invalid
  if (response.status === 401 && !isRetry) {
    // Try to refresh the token
    const newToken = await tokenManager.refreshToken();

    if (newToken) {
      // Retry the request with the new token
      return fetchApi<T>(endpoint, options, true);
    }

    // Token refresh failed, redirect to login
    if (typeof window !== 'undefined') {
      // Clear any invalid tokens
      tokenManager.clearTokens();

      // Redirect to login page (but avoid redirect loop on login page)
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }

    // Throw error after failed refresh
    throw new ApiError('Session expired. Please login again.', 401);
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

  // Handle 401 Unauthorized
  if (response.status === 401 && !isRetry) {
    const newToken = await tokenManager.refreshToken();

    if (newToken) {
      return fetchApiUpload<T>(endpoint, options, true);
    }

    if (typeof window !== 'undefined') {
      tokenManager.clearTokens();
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }

    throw new ApiError('Session expired. Please login again.', 401);
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
  async uploadFile(file: File, metadata?: Record<string, string>): Promise<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('metadata', JSON.stringify(metadata || {}));

    return fetchApiUpload<FileUploadResponse>(`${API_ENDPOINTS.documents}/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  async getDocuments(): Promise<DocumentListResponse> {
    return fetchApi<DocumentListResponse>(API_ENDPOINTS.documents);
  },

  async deleteDocument(documentId: string): Promise<void> {
    await fetchApi(`${API_ENDPOINTS.documents}/${documentId}`, { method: 'DELETE' });
  },

  // Session
  async clearSession(sessionId: string): Promise<void> {
    await fetchApi(API_ENDPOINTS.session(sessionId), {
      method: 'DELETE',
    });
  },
};
