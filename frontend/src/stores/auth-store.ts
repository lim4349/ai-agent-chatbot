import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User, LoginRequest, RegisterRequest } from '@/types';
import { tokenManager } from '@/lib/token-manager';

interface AuthStore {
  // State
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  register: (credentials: RegisterRequest) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  clearError: () => void;
  updateUser: (user: User) => void;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Authentication Store using Zustand
 * Manages user authentication state and provides login/logout functionality
 */
export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // Initial state
      isAuthenticated: false,
      user: null,
      isLoading: false,
      error: null,

      /**
       * Login with email and password
       */
      login: async (credentials: LoginRequest) => {
        set({ isLoading: true, error: null });

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentials),
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Login failed' }));
            throw new Error(errorData.error || errorData.detail || 'Login failed');
          }

          const data = await response.json();

          // Store tokens
          tokenManager.setToken(data.access_token, credentials.remember ?? false);
          tokenManager.setRefreshToken(data.refresh_token);

          // Update state
          set({
            isAuthenticated: true,
            user: data.user,
            isLoading: false,
            error: null,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Login failed';
          set({
            isAuthenticated: false,
            user: null,
            isLoading: false,
            error: errorMessage,
          });
          throw error;
        }
      },

      /**
       * Register a new user
       */
      register: async (credentials: RegisterRequest) => {
        set({ isLoading: true, error: null });

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentials),
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Registration failed' }));
            throw new Error(errorData.error || errorData.detail || 'Registration failed');
          }

          const data = await response.json();

          // Store tokens
          tokenManager.setToken(data.access_token, false); // Don't persist session on registration
          tokenManager.setRefreshToken(data.refresh_token);

          // Update state
          set({
            isAuthenticated: true,
            user: data.user,
            isLoading: false,
            error: null,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Registration failed';
          set({
            isAuthenticated: false,
            user: null,
            isLoading: false,
            error: errorMessage,
          });
          throw error;
        }
      },

      /**
       * Logout and clear authentication state
       */
      logout: () => {
        tokenManager.clearTokens();
        set({
          isAuthenticated: false,
          user: null,
          error: null,
        });
      },

      /**
       * Check authentication status on app load
       * Validates stored token and updates authentication state
       */
      checkAuth: async () => {
        const token = tokenManager.getToken();

        if (!token) {
          set({ isAuthenticated: false, user: null });
          return;
        }

        // Check if token is expired
        if (tokenManager.isTokenExpired(token)) {
          // Try to refresh the token
          const newToken = await tokenManager.refreshToken();
          if (!newToken) {
            set({ isAuthenticated: false, user: null });
            return;
          }
        }

        // Token is valid, get user info from token payload
        const payload = tokenManager.getTokenPayload();
        if (payload) {
          const user: User = {
            id: String(payload.user_id || payload.sub || ''),
            email: String(payload.email || ''),
            username: payload.username ? String(payload.username) : undefined,
            full_name: payload.full_name ? String(payload.full_name) : undefined,
          };

          set({
            isAuthenticated: true,
            user,
          });
        } else {
          // Invalid token payload
          tokenManager.clearTokens();
          set({ isAuthenticated: false, user: null });
        }
      },

      /**
       * Clear any authentication errors
       */
      clearError: () => {
        set({ error: null });
      },

      /**
       * Update user information
       */
      updateUser: (user: User) => {
        set({ user });
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Only persist user info, not authentication state
        // Authentication state should be derived from token validity
        user: state.user,
      }),
    }
  )
);

/**
 * Hook to get current authentication status
 * Returns a boolean indicating if the user is authenticated
 */
export const useIsAuthenticated = () => {
  return useAuthStore((state) => state.isAuthenticated);
};

/**
 * Hook to get current user
 * Returns the user object or null if not authenticated
 */
export const useCurrentUser = () => {
  return useAuthStore((state) => state.user);
};

/**
 * Hook to get authentication actions
 * Returns login, logout, register, and checkAuth functions
 */
export const useAuthActions = () => {
  return useAuthStore((state) => ({
    login: state.login,
    logout: state.logout,
    register: state.register,
    checkAuth: state.checkAuth,
    clearError: state.clearError,
  }));
};

/**
 * Hook to get authentication loading state
 */
export const useAuthLoading = () => {
  return useAuthStore((state) => state.isLoading);
};

/**
 * Hook to get authentication error
 */
export const useAuthError = () => {
  return useAuthStore((state) => state.error);
};
