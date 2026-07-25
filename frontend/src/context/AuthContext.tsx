import { getMe } from '@/api/generated/users/users.ts';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { AXIOS_INSTANCE } from '../api/axios-instance';
import { useLogin } from '../api/generated/auth/auth';
import type { UserDetailsResponse } from '../api/generated/model';
import { getRegisterMutationOptions } from '../api/generated/users/users';
import { clearTokens, getAccessToken, setAccessToken } from '../api/token-manager';

interface AuthContextType {
  user: UserDetailsResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserDetailsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const performTokenRefreshRef = useRef<(() => Promise<boolean>) | null>(null);

  const loginMutation = useLogin();
  const registerMutation = useMutation(getRegisterMutationOptions());

  // Clear scheduled refresh
  const clearRefreshTimeout = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
      refreshTimeoutRef.current = null;
    }
  }, []);

  // Perform token refresh using httpOnly cookie and schedule next refresh
  const performTokenRefresh = useCallback(async (): Promise<boolean> => {
    try {
      const response = await AXIOS_INSTANCE.post<{
        access_token: string;
        refresh_token: string;
        expires_in: number;
      }>('/api/v1/auth/refresh', null, {
        withCredentials: true,
      });

      const { access_token, expires_in } = response.data;
      setAccessToken(access_token, expires_in);

      // Schedule next refresh at 75% of token lifetime
      const refreshTime = expires_in * 0.75 * 1000;
      if (refreshTime > 0) {
        clearRefreshTimeout();
        refreshTimeoutRef.current = setTimeout(() => {
          void performTokenRefreshRef.current?.();
        }, refreshTime);
      }

      return true;
    } catch {
      clearTokens();
      setUser(null);
      return false;
    }
  }, [clearRefreshTimeout]);

  // Keep ref up-to-date with latest function
  useEffect(() => {
    performTokenRefreshRef.current = performTokenRefresh;
  }, [performTokenRefresh]);

  // Helper to schedule next refresh (for login/register)
  const scheduleNextRefresh = useCallback(
    (expiresIn: number) => {
      const refreshTime = expiresIn * 0.75 * 1000;
      if (refreshTime > 0) {
        clearRefreshTimeout();
        refreshTimeoutRef.current = setTimeout(() => {
          void performTokenRefreshRef.current?.();
        }, refreshTime);
      }
    },
    [clearRefreshTimeout]
  );

  const logout = useCallback(async () => {
    clearRefreshTimeout();

    try {
      // Call logout endpoint to clear httpOnly cookie
      await AXIOS_INSTANCE.post('/api/v1/auth/logout', null, {
        withCredentials: true,
      });
    } catch {
      // Ignore errors, proceed with client-side cleanup
    }

    clearTokens();
    setUser(null);
    queryClient.clear();
    navigate({ to: '/login' });
  }, [navigate, queryClient, clearRefreshTimeout]);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await getMe();
      setUser(userData);
    } catch {
      // If refresh fails, user might be logged out
      await logout();
    }
  }, [logout]);

  // On mount: clean up legacy localStorage and try to restore session via refresh
  useEffect(() => {
    const initAuth = async () => {
      // Try to restore session from httpOnly cookie
      const success = await performTokenRefresh();
      if (success) {
        try {
          const userData = await getMe();
          setUser(userData);
        } catch {
          // Token was refreshed but user fetch failed
          clearTokens();
        }
      }

      setIsLoading(false);
    };

    initAuth();

    // Cleanup on unmount
    return () => {
      clearRefreshTimeout();
    };
  }, [clearRefreshTimeout, performTokenRefresh]);

  const login = async (email: string, password: string) => {
    const response = await loginMutation.mutateAsync({
      data: { username: email, password },
    });

    // Store token in memory only
    setAccessToken(response.access_token, response.expires_in);
    scheduleNextRefresh(response.expires_in);

    // Fetch user details after login
    const userData = await getMe();
    setUser(userData);
  };

  const register = async (email: string, password: string) => {
    const response = await registerMutation.mutateAsync({
      data: { email, password },
    });

    // Store token in memory only
    setAccessToken(response.access_token, response.expires_in);
    scheduleNextRefresh(response.expires_in);

    // Fetch user details after registration
    const userData = await getMe();
    setUser(userData);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!getAccessToken() && !!user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
