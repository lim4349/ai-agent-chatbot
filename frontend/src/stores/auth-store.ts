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
  logout: () => Promise<void>;
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
       * Login with email and password using Supabase
       */
      login: async (credentials: LoginRequest) => {
        set({ isLoading: true, error: null });

        try {
          const { supabaseAuth } = await import('@/lib/supabase');
          const data = await supabaseAuth.signIn(credentials.email, credentials.password);

          if (!data.session || !data.user) {
            throw new Error('Login failed');
          }

          // Extract user data from Supabase user
          const user: User = {
            id: data.user.id,
            email: data.user.email || '',
            username: data.user.user_metadata?.username,
            full_name: data.user.user_metadata?.full_name,
            avatar_url: data.user.user_metadata?.avatar_url,
            created_at: data.user.created_at,
            updated_at: data.user.updated_at,
          };

          // Store session token for backend API calls
          tokenManager.setToken(data.session.access_token, credentials.remember ?? false);
          tokenManager.setRefreshToken(data.session.refresh_token);

          // Update state
          set({
            isAuthenticated: true,
            user,
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
       * Register a new user using Supabase
       */
      register: async (credentials: RegisterRequest) => {
        set({ isLoading: true, error: null });

        try {
          // Build user metadata
          const metadata: Record<string, unknown> = {};
          if (credentials.full_name) metadata.full_name = credentials.full_name;
          if (credentials.username) metadata.username = credentials.username;

          const { supabaseAuth } = await import('@/lib/supabase');
          const data = await supabaseAuth.signUp(credentials.email, credentials.password, metadata);

          if (!data.session || !data.user) {
            throw new Error('Registration failed');
          }

          // Extract user data from Supabase user
          const user: User = {
            id: data.user.id,
            email: data.user.email || '',
            username: data.user.user_metadata?.username,
            full_name: data.user.user_metadata?.full_name,
            avatar_url: data.user.user_metadata?.avatar_url,
            created_at: data.user.created_at,
            updated_at: data.user.updated_at,
          };

          // Store session token for backend API calls
          tokenManager.setToken(data.session.access_token, false);
          tokenManager.setRefreshToken(data.session.refresh_token);

          // Update state
          set({
            isAuthenticated: true,
            user,
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
       * Logout and clear authentication state using Supabase
       */
      logout: async () => {
        const { supabaseAuth } = await import('@/lib/supabase');
        await supabaseAuth.signOut();
        tokenManager.clearTokens();
        set({
          isAuthenticated: false,
          user: null,
          error: null,
        });
      },

      /**
       * Check authentication status on app load using Supabase
       * Validates Supabase session and updates authentication state
       */
      checkAuth: async () => {
        try {
          const { supabaseAuth } = await import('@/lib/supabase');
          const session = await supabaseAuth.getSession();

          if (!session) {
            set({ isAuthenticated: false, user: null });
            tokenManager.clearTokens();
            return;
          }

          // Extract user data from Supabase session
          const user: User = {
            id: session.user.id,
            email: session.user.email || '',
            username: session.user.user_metadata?.username,
            full_name: session.user.user_metadata?.full_name,
            avatar_url: session.user.user_metadata?.avatar_url,
            created_at: session.user.created_at,
            updated_at: session.user.updated_at,
          };

          // Store session token for backend API calls
          tokenManager.setToken(session.access_token, true);
          tokenManager.setRefreshToken(session.refresh_token);

          set({
            isAuthenticated: true,
            user,
          });
        } catch (error) {
          console.error('Auth check failed:', error);
          set({ isAuthenticated: false, user: null });
          tokenManager.clearTokens();
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
