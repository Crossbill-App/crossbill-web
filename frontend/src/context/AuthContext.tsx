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
import { AXIOS_INSTANCE, refreshSession, SessionExpiredError } from '../api/axios-instance';
import { useLogin } from '../api/generated/auth/auth';
import type { UserDetailsResponse } from '../api/generated/model';
import { getRegisterMutationOptions } from '../api/generated/users/users';
import {
  clearTokens,
  getAccessToken,
  getTokenExpiresAt,
  setAccessToken,
} from '../api/token-manager';

interface AuthContextType {
  user: UserDetailsResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

// Refresh at three quarters of the token's life, leaving room for the refresh
// itself to fail and be retried before anything actually expires.
const REFRESH_AT_FRACTION_OF_LIFETIME = 0.75;

// Backoff for a refresh that failed without the server rejecting the session.
// The refresh cookie is good for weeks, so waiting out a bad network is nearly
// always the right move; the last delay repeats for as long as it takes.
const RETRY_DELAYS_MS = [5_000, 15_000, 60_000];

// Returning to the foreground with a token this close to expiry triggers a
// refresh straight away. iOS suspends timers in a backgrounded PWA, so the
// scheduled refresh is often long overdue on resume, and without this the
// queries that refetch on focus would all 401 at once.
const REFRESH_ON_FOCUS_MARGIN_MS = 60_000;

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserDetailsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryIndexRef = useRef(0);
  const initialRestorePendingRef = useRef(true);
  const syncSessionRef = useRef<(() => Promise<void>) | null>(null);

  const loginMutation = useLogin();
  const registerMutation = useMutation(getRegisterMutationOptions());

  const clearRefreshTimeout = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
      refreshTimeoutRef.current = null;
    }
  }, []);

  const scheduleRefreshIn = useCallback(
    (ms: number) => {
      clearRefreshTimeout();
      if (ms <= 0) {
        return;
      }
      refreshTimeoutRef.current = setTimeout(() => {
        void syncSessionRef.current?.();
      }, ms);
    },
    [clearRefreshTimeout]
  );

  const scheduleRefreshBeforeExpiry = useCallback(
    (expiresIn: number) => {
      retryIndexRef.current = 0;
      scheduleRefreshIn(expiresIn * REFRESH_AT_FRACTION_OF_LIFETIME * 1000);
    },
    [scheduleRefreshIn]
  );

  const settleInitialRestore = useCallback(() => {
    if (!initialRestorePendingRef.current) {
      return;
    }
    initialRestorePendingRef.current = false;
    setIsLoading(false);
  }, []);

  /**
   * Bring the session up to date and schedule the next round.
   *
   * Runs on mount, on the scheduled tick, and when the app returns to the
   * foreground. Those can overlap freely: `refreshSession` is single-flight, so
   * concurrent triggers share one request rather than presenting the same
   * refresh token twice and tripping replay detection.
   */
  const syncSession = useCallback(async () => {
    try {
      const { expiresIn } = await refreshSession();
      scheduleRefreshBeforeExpiry(expiresIn);
    } catch (error) {
      if (error instanceof SessionExpiredError) {
        clearRefreshTimeout();
        setUser(null);
        settleInitialRestore();
        return;
      }

      // The session is very likely still valid — the request just never landed.
      // Keep it and try again instead of presenting a login form that the
      // user's credentials were never the problem for.
      const isFirstFailure = retryIndexRef.current === 0;
      scheduleRefreshIn(RETRY_DELAYS_MS[retryIndexRef.current]);
      retryIndexRef.current = Math.min(retryIndexRef.current + 1, RETRY_DELAYS_MS.length - 1);

      // Ride out one retry before rendering: a phone whose network is still
      // coming up recovers inside it, and waiting longer only shows a spinner
      // the user cannot act on.
      if (!isFirstFailure) {
        settleInitialRestore();
      }
      return;
    }

    if (!user) {
      try {
        setUser(await getMe());
      } catch {
        clearTokens();
        setUser(null);
      }
    }
    settleInitialRestore();
  }, [
    clearRefreshTimeout,
    scheduleRefreshIn,
    scheduleRefreshBeforeExpiry,
    settleInitialRestore,
    user,
  ]);

  useEffect(() => {
    syncSessionRef.current = syncSession;
  }, [syncSession]);

  // Restore the session from the httpOnly refresh cookie on mount. Reached
  // through the ref, which the effect above has already filled: the state
  // updates happen after the first await, never while this effect is running.
  useEffect(() => {
    void syncSessionRef.current?.();
    return clearRefreshTimeout;
  }, [clearRefreshTimeout]);

  useEffect(() => {
    const refreshIfStale = () => {
      if (document.visibilityState !== 'visible' || !user) {
        return;
      }
      const expiresAt = getTokenExpiresAt();
      if (expiresAt !== null && expiresAt - Date.now() > REFRESH_ON_FOCUS_MARGIN_MS) {
        return;
      }
      void syncSessionRef.current?.();
    };

    document.addEventListener('visibilitychange', refreshIfStale);
    return () => document.removeEventListener('visibilitychange', refreshIfStale);
  }, [user]);

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
      setUser(await getMe());
    } catch {
      // Whether the session is still good is not this call's to decide: a dead
      // token surfaces as a 401 the response interceptor already acts on, and
      // anything else is a transient failure the stale user data survives.
    }
  }, []);

  const startSession = useCallback(
    async (accessToken: string, expiresIn: number) => {
      setAccessToken(accessToken, expiresIn);
      scheduleRefreshBeforeExpiry(expiresIn);
      setUser(await getMe());
    },
    [scheduleRefreshBeforeExpiry]
  );

  const login = async (email: string, password: string) => {
    const response = await loginMutation.mutateAsync({
      data: { username: email, password },
    });
    await startSession(response.access_token, response.expires_in);
  };

  const register = async (email: string, password: string) => {
    const response = await registerMutation.mutateAsync({
      data: { email, password },
    });
    await startSession(response.access_token, response.expires_in);
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
