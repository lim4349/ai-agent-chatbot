'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';

/**
 * Authentication Provider Component
 * Initializes authentication state on app load and sets up token refresh logic
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isInitialized, setIsInitialized] = useState(false);
  const checkAuth = useAuthStore((state) => state.checkAuth);

  useEffect(() => {
    // Check authentication status on mount
    const initializeAuth = async () => {
      try {
        await checkAuth();
      } catch (error) {
        console.error('Auth initialization failed:', error);
      } finally {
        setIsInitialized(true);
      }
    };

    initializeAuth();

    // Setup token auto-refresh interval
    // Check every minute if token needs refresh
    const refreshInterval = setInterval(async () => {
      const { tokenManager } = await import('@/lib/token-manager');
      if (tokenManager.hasValidToken()) {
        const timeUntilExpiry = tokenManager.getTimeUntilExpiration();

        // Refresh if token expires in less than 10 minutes
        if (timeUntilExpiry > 0 && timeUntilExpiry < 10 * 60 * 1000) {
          console.log('Token expiring soon, refreshing...');
          await tokenManager.refreshToken();
        }
      }
    }, 60 * 1000); // Check every minute

    return () => {
      clearInterval(refreshInterval);
    };
  }, [checkAuth]);

  // Prevent flash of unauthenticated content
  if (!isInitialized) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
