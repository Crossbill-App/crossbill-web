import Axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { clearTokens, getAccessToken, setAccessToken } from './token-manager';

// Default baseURL - can be overridden by setting AXIOS_INSTANCE.defaults.baseURL
// In development, this points to the local backend server
export const AXIOS_INSTANCE = Axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enable cookie handling for refresh tokens
});

/**
 * The server rejected the refresh token itself: the session is over and only
 * signing in again will fix it.
 *
 * Every other refresh failure — no network, a 5xx, a rate limit — leaves the
 * session perfectly valid and must not be mistaken for this one. Treating them
 * alike is why a phone that briefly lost signal came back to a login form.
 */
export class SessionExpiredError extends Error {
  constructor() {
    super('The session has expired');
    this.name = 'SessionExpiredError';
  }
}

export interface RefreshResult {
  accessToken: string;
  expiresIn: number;
}

interface RefreshResponseBody {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

const REFRESH_URL = '/api/v1/auth/refresh';

// Two quick retries, deliberately well inside the server's rotation grace
// window: a refresh whose response was lost still spent the token server-side,
// and only a retry landing within that window is answered with the replacement
// rather than being read as a replay.
const TRANSIENT_RETRY_DELAYS_MS = [500, 2000];

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Refreshing rotates the refresh token, so two calls in flight at once present
// the same token twice and the loser looks like a stolen-token replay — which
// ends the whole session. Every caller shares one attempt: the 401 interceptor,
// the scheduled refresh, and the app returning to the foreground all collapse
// into this single promise.
let inFlight: Promise<RefreshResult> | null = null;

export function refreshSession(): Promise<RefreshResult> {
  inFlight ??= runRefresh().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function runRefresh(): Promise<RefreshResult> {
  for (let attempt = 0; ; attempt++) {
    try {
      const { data } = await AXIOS_INSTANCE.post<RefreshResponseBody>(REFRESH_URL, null, {
        withCredentials: true,
      });
      setAccessToken(data.access_token, data.expires_in);
      return { accessToken: data.access_token, expiresIn: data.expires_in };
    } catch (error) {
      if (isSessionRejection(error)) {
        throw new SessionExpiredError();
      }
      if (attempt >= TRANSIENT_RETRY_DELAYS_MS.length || !isRetryable(error)) {
        throw error;
      }
      await delay(TRANSIENT_RETRY_DELAYS_MS[attempt]);
    }
  }
}

function isSessionRejection(error: unknown): boolean {
  return Axios.isAxiosError(error) && error.response?.status === 401;
}

// No response at all means the request never completed, which says nothing
// about the session. A 5xx is the server failing, not the token. A 429 is not
// retried here — hammering a rate limit only deepens it — but it is not a
// logout either, so it propagates as an ordinary error.
function isRetryable(error: unknown): boolean {
  if (!Axios.isAxiosError(error)) {
    return false;
  }
  const status = error.response?.status;
  return status === undefined || status >= 500;
}

function endSession(): void {
  clearTokens();
  if (!window.location.pathname.includes('/login')) {
    window.location.href = '/login';
  }
}

// Add request interceptor for auth tokens
AXIOS_INSTANCE.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor for token refresh on 401
AXIOS_INSTANCE.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    // Only handle 401 errors that haven't been retried
    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    // The auth endpoints answer 401 about the credentials themselves, so
    // refreshing and replaying them would only loop.
    if (originalRequest.url?.includes('/auth/')) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      const { accessToken } = await refreshSession();
      originalRequest.headers.Authorization = `Bearer ${accessToken}`;
      return await AXIOS_INSTANCE(originalRequest);
    } catch (refreshError) {
      // Only a rejected refresh token ends the session. Anything else leaves
      // the caller to handle a failed request the way it would any other.
      if (refreshError instanceof SessionExpiredError) {
        endSession();
      }
      return Promise.reject(refreshError);
    }
  }
);

export const axiosInstance = <T>(config: AxiosRequestConfig): Promise<T> => {
  const source = Axios.CancelToken.source();
  const promise = AXIOS_INSTANCE({
    ...config,
    cancelToken: source.token,
  }).then(({ data }) => data);

  // @ts-expect-error - Adding cancel method to promise for Orval
  promise.cancel = () => {
    source.cancel('Query was cancelled');
  };

  return promise;
};
