'use client';

/**
 * Example Component: Authentication Usage
 *
 * This component demonstrates how to use the JWT authentication system
 * in your AI Agent Chatbot application.
 */

import { useState } from 'react';
import {
  useIsAuthenticated,
  useCurrentUser,
  useAuthActions,
  useAuthLoading,
  useAuthError,
} from '@/stores/auth-store';
import { ProtectedRoute } from '@/components/protected-route';

/**
 * Login Form Component
 * Demonstrates user login with email/password
 */
export function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const { login } = useAuthActions();
  const isLoading = useAuthLoading();
  const error = useAuthError();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login({ email, password, remember });
      // Redirect or show success message
      console.log('Login successful');
    } catch (err) {
      console.error('Login failed:', err);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
          required
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
          required
        />
      </div>

      <div className="flex items-center">
        <input
          id="remember"
          type="checkbox"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300"
        />
        <label htmlFor="remember" className="ml-2 block text-sm">
          Remember me
        </label>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={isLoading}
        className="w-full rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {isLoading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
}

/**
 * User Profile Component
 * Displays current user information and logout button
 */
export function UserProfile() {
  const user = useCurrentUser();
  const { logout } = useAuthActions();

  if (!user) return null;

  return (
    <div className="rounded-lg bg-gray-100 p-6">
      <h2 className="text-lg font-semibold">Welcome, {user.email}</h2>
      {user.username && <p className="text-sm text-gray-600">@{user.username}</p>}
      {user.full_name && <p className="text-sm text-gray-600">{user.full_name}</p>}

      <button
        onClick={logout}
        className="mt-4 rounded-md bg-red-600 px-4 py-2 text-white hover:bg-red-700"
      >
        Logout
      </button>
    </div>
  );
}

/**
 * Protected Content Component
 * Only visible when user is authenticated
 */
export function ProtectedContent() {
  return (
    <ProtectedRoute>
      <div className="space-y-6">
        <UserProfile />
        <div className="rounded-lg bg-blue-50 p-6">
          <h3 className="font-semibold">Protected Content</h3>
          <p className="mt-2 text-sm text-gray-700">
            This content is only visible to authenticated users.
          </p>
        </div>
      </div>
    </ProtectedRoute>
  );
}

/**
 * Authentication Status Component
 * Shows current authentication status
 */
export function AuthStatus() {
  const isAuthenticated = useIsAuthenticated();
  const user = useCurrentUser();
  const isLoading = useAuthLoading();

  if (isLoading) {
    return <div className="text-sm text-gray-600">Checking authentication...</div>;
  }

  return (
    <div className="rounded-lg bg-gray-100 p-4">
      <div className="flex items-center space-x-2">
        <div
          className={`h-3 w-3 rounded-full ${
            isAuthenticated ? 'bg-green-500' : 'bg-red-500'
          }`}
        />
        <span className="text-sm font-medium">
          {isAuthenticated ? 'Authenticated' : 'Not Authenticated'}
        </span>
      </div>
      {user && (
        <div className="mt-2 text-sm text-gray-600">
          Logged in as: {user.email}
        </div>
      )}
    </div>
  );
}

/**
 * Main Example Component
 * Demonstrates complete authentication flow
 */
export function AuthExample() {
  const isAuthenticated = useIsAuthenticated();

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <h1 className="text-2xl font-bold">Authentication Example</h1>

      <AuthStatus />

      {!isAuthenticated ? (
        <div className="rounded-lg bg-white p-6 shadow-md">
          <h2 className="mb-4 text-lg font-semibold">Login to Continue</h2>
          <LoginForm />
        </div>
      ) : (
        <ProtectedContent />
      )}

      <div className="rounded-lg bg-yellow-50 p-4">
        <h3 className="font-semibold text-yellow-800">Usage Notes</h3>
        <ul className="mt-2 list-inside list-disc text-sm text-yellow-700">
          <li>Tokens are automatically refreshed before expiration</li>
          <li>API calls include authentication headers automatically</li>
          <li>Protected routes redirect to login if needed</li>
          <li>Session persists based on &quot;Remember me&quot; checkbox</li>
        </ul>
      </div>
    </div>
  );
}

/**
 * Example: Using API with Authentication
 *
 * All API calls from the api module automatically include
 * the JWT token in the Authorization header:
 *
 * import { api } from '@/lib/api';
 *
 * // This will include the authentication token
 * const documents = await api.getDocuments();
 *
 * // Token refresh is handled automatically on 401 errors
 * const health = await api.getHealth();
 */

export default AuthExample;
