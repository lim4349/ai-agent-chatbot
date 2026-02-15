/**
 * JWT Token Manager Test Suite
 * Tests for token management functionality
 */

import { tokenManager } from '../token-manager';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

// Mock window object
Object.defineProperty(global, 'window', {
  value: {
    localStorage: localStorageMock,
    sessionStorage: localStorageMock,
  },
  writable: true,
});

describe('tokenManager', () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  describe('getToken', () => {
    it('should return null when no token is stored', () => {
      expect(tokenManager.getToken()).toBeNull();
    });

    it('should return token from localStorage', () => {
      const testToken = 'test.jwt.token';
      tokenManager.setToken(testToken, true);
      expect(tokenManager.getToken()).toBe(testToken);
    });
  });

  describe('setToken', () => {
    it('should store token in localStorage when rememberMe is true', () => {
      const testToken = 'test.jwt.token';
      tokenManager.setToken(testToken, true);
      expect(localStorageMock.getItem('auth_token')).toBe(testToken);
    });
  });

  describe('clearTokens', () => {
    it('should remove all tokens', () => {
      tokenManager.setToken('access.token', true);
      tokenManager.setRefreshToken('refresh.token');
      tokenManager.clearTokens();
      expect(tokenManager.getToken()).toBeNull();
      expect(tokenManager.getRefreshToken()).toBeNull();
    });
  });

  describe('parseToken', () => {
    it('should parse valid JWT token', () => {
      // Create a valid JWT payload
      const payload = { exp: Date.now() / 1000 + 3600, user_id: '123', email: 'test@example.com' };
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
      const body = btoa(JSON.stringify(payload));
      const signature = 'signature';
      const token = `${header}.${body}.${signature}`;

      const parsed = tokenManager.parseToken(token);
      expect(parsed?.user_id).toBe('123');
      expect(parsed?.email).toBe('test@example.com');
    });

    it('should return null for invalid token', () => {
      expect(tokenManager.parseToken('invalid')).toBeNull();
    });
  });

  describe('isTokenExpired', () => {
    it('should return true for expired token', () => {
      const payload = { exp: Date.now() / 1000 - 3600 }; // Expired 1 hour ago
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
      const body = btoa(JSON.stringify(payload));
      const token = `${header}.${body}.signature`;

      expect(tokenManager.isTokenExpired(token)).toBe(true);
    });

    it('should return false for valid token', () => {
      const payload = { exp: Date.now() / 1000 + 3600 }; // Expires in 1 hour
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
      const body = btoa(JSON.stringify(payload));
      const token = `${header}.${body}.signature`;

      expect(tokenManager.isTokenExpired(token)).toBe(false);
    });
  });

  describe('getTokenPayload', () => {
    it('should return payload for stored token', () => {
      const payload = { exp: Date.now() / 1000 + 3600, user_id: '123', email: 'test@example.com' };
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
      const body = btoa(JSON.stringify(payload));
      const token = `${header}.${body}.signature`;

      tokenManager.setToken(token);
      const result = tokenManager.getTokenPayload();
      expect(result?.user_id).toBe('123');
    });

    it('should return null when no token stored', () => {
      expect(tokenManager.getTokenPayload()).toBeNull();
    });
  });

  describe('hasValidToken', () => {
    it('should return false when no token', () => {
      expect(tokenManager.hasValidToken()).toBe(false);
    });

    it('should return false when token is expired', () => {
      const payload = { exp: Date.now() / 1000 - 3600 };
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
      const body = btoa(JSON.stringify(payload));
      const token = `${header}.${body}.signature`;

      tokenManager.setToken(token);
      expect(tokenManager.hasValidToken()).toBe(false);
    });

    it('should return true when token is valid', () => {
      const payload = { exp: Date.now() / 1000 + 3600 };
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
      const body = btoa(JSON.stringify(payload));
      const token = `${header}.${body}.signature`;

      tokenManager.setToken(token);
      expect(tokenManager.hasValidToken()).toBe(true);
    });
  });
});
