const TOKEN_KEY = 'auth_token';

export interface TokenPayload {
  exp: number;
  iat?: number;
  sub?: string;
  user_id?: string;
  email?: string;
  [key: string]: string | number | boolean | undefined;
}

/**
 * Token storage utility for optional bearer-token API calls.
 * The current product flow is guest-first and does not expose login UI.
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
   * Store an access token.
   * @param token - Bearer token to attach to API requests
   * @param rememberMe - If true, stores in localStorage; otherwise sessionStorage
   */
  setToken(token: string, rememberMe: boolean = false): void {
    if (typeof window === 'undefined') return;

    const storage = rememberMe ? localStorage : sessionStorage;
    storage.setItem(TOKEN_KEY, token);
  },

  /**
   * Clear stored access tokens from both localStorage and sessionStorage.
   */
  clearTokens(): void {
    if (typeof window === 'undefined') return;

    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  },

  /**
   * Check if a token is expired
   * @param token - JWT-like token to check
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
   * Parse and decode a JWT-like token payload.
   * @param token - Token to parse
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
   * Check if there's a valid (non-expired) token
   */
  hasValidToken(): boolean {
    const token = this.getToken();
    return token !== null && !this.isTokenExpired(token);
  },
};
