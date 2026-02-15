const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export interface TokenPayload {
  exp: number;
  iat?: number;
  sub?: string;
  user_id?: string;
  email?: string;
  [key: string]: string | number | boolean | undefined;
}

/**
 * Token Manager for JWT authentication
 * Handles token storage, validation, and refresh logic
 */
export const tokenManager = {
  /**
   * Get the stored access token from localStorage or sessionStorage
   */
  getToken(): string | null {
    if (typeof window === 'undefined') return null;

    // Check sessionStorage first (current session only)
    const sessionToken = sessionStorage.getItem(TOKEN_KEY);
    if (sessionToken) return sessionToken;

    // Fall back to localStorage (persistent)
    return localStorage.getItem(TOKEN_KEY);
  },

  /**
   * Store the access token
   * @param token - The JWT access token
   * @param rememberMe - If true, stores in localStorage; otherwise sessionStorage
   */
  setToken(token: string, rememberMe: boolean = false): void {
    if (typeof window === 'undefined') return;

    const storage = rememberMe ? localStorage : sessionStorage;
    storage.setItem(TOKEN_KEY, token);
  },

  /**
   * Get the stored refresh token
   */
  getRefreshToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  /**
   * Store the refresh token (always in localStorage for persistence)
   */
  setRefreshToken(token: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  },

  /**
   * Clear all tokens from both localStorage and sessionStorage
   */
  clearTokens(): void {
    if (typeof window === 'undefined') return;

    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  /**
   * Check if a token is expired
   * @param token - JWT token to check
   * @returns true if token is expired or invalid, false otherwise
   */
  isTokenExpired(token: string): boolean {
    try {
      const payload = this.parseToken(token);
      if (!payload || !payload.exp) return true;

      // Check if token expires within the next minute (buffer for network latency)
      const expirationTime = payload.exp * 1000;
      const now = Date.now();
      const oneMinute = 60 * 1000;

      return expirationTime < (now + oneMinute);
    } catch {
      return true;
    }
  },

  /**
   * Parse and decode JWT token payload
   * @param token - JWT token to parse
   * @returns Decoded token payload or null if invalid
   */
  parseToken(token: string): TokenPayload | null {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return null;

      // Decode base64url payload
      const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );

      return JSON.parse(jsonPayload);
    } catch {
      return null;
    }
  },

  /**
   * Get the payload of the currently stored token
   * @returns Token payload or null if no valid token
   */
  getTokenPayload(): TokenPayload | null {
    const token = this.getToken();
    if (!token) return null;
    return this.parseToken(token);
  },

  /**
   * Get the user ID from the current token
   */
  getUserId(): string | null {
    const payload = this.getTokenPayload();
    return payload?.user_id || payload?.sub || null;
  },

  /**
   * Get the user email from the current token
   */
  getUserEmail(): string | null {
    const payload = this.getTokenPayload();
    return payload?.email || null;
  },

  /**
   * Check if there's a valid (non-expired) token
   */
  hasValidToken(): boolean {
    const token = this.getToken();
    return token !== null && !this.isTokenExpired(token);
  },

  /**
   * Refresh the access token using the refresh token
   * @returns New access token or null if refresh failed
   */
  async refreshToken(): Promise<string | null> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return null;

    try {
      // Import API_BASE_URL dynamically to avoid circular dependencies
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (response.ok) {
        const data = await response.json();

        // Store new tokens
        this.setToken(data.access_token, data.remember ?? true);
        if (data.refresh_token) {
          this.setRefreshToken(data.refresh_token);
        }

        return data.access_token;
      }

      // Refresh failed, clear tokens
      this.clearTokens();
      return null;
    } catch (error) {
      console.error('Token refresh failed:', error);
      this.clearTokens();
      return null;
    }
  },

  /**
   * Calculate time until token expires in milliseconds
   * @returns Milliseconds until expiration, or 0 if expired/invalid
   */
  getTimeUntilExpiration(): number {
    const payload = this.getTokenPayload();
    if (!payload || !payload.exp) return 0;

    const expirationTime = payload.exp * 1000;
    const now = Date.now();

    return Math.max(0, expirationTime - now);
  },

  /**
   * Setup automatic token refresh before expiration
   * @param callback - Function to call when refresh is needed
   * @returns Cleanup function to clear the timeout
   */
  setupAutoRefresh(callback: () => void): () => void {
    const timeUntilExpiry = this.getTimeUntilExpiration();

    // Refresh 5 minutes before expiration
    const refreshTime = Math.max(0, timeUntilExpiry - 5 * 60 * 1000);

    const timeoutId = setTimeout(() => {
      callback();
    }, refreshTime);

    // Return cleanup function
    return () => clearTimeout(timeoutId);
  },
};

/**
 * Higher-order function to wrap API calls with token refresh logic
 */
export async function withTokenRefresh<T>(
  apiCall: () => Promise<T>
): Promise<T> {
  try {
    return await apiCall();
  } catch (error: unknown) {
    const err = error as { status?: number; message?: string };
    // If 401 Unauthorized, try to refresh token and retry
    if (err.status === 401 || err.message?.includes('401')) {
      const newToken = await tokenManager.refreshToken();
      if (newToken) {
        return await apiCall();
      }
    }
    throw error;
  }
}
