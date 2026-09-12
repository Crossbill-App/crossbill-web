/**
 * Keeps a publication cookie alive for one book while the reader is open.
 *
 * The navigator loads a book's resources into iframes, and an iframe load
 * carries cookies and nothing else — never the in-memory access token, which
 * is what this second credential buys. A 401 belongs to the axios interceptor,
 * not here: it refreshes and replays, and only a dead session reaches us.
 *
 * Nothing here resets when `bookId` changes: the shell is keyed by book, so a
 * different book is a different component with its own state.
 */
import { startPublicationSession } from '@/api/generated/readium/readium.ts';
import { useEffect, useRef, useState } from 'react';

// The cookie is httpOnly, so the page never sees it expire and can only go by
// the `expires_in` it was told; four fifths of that leaves room for a slow post.
const REFRESH_AT = 0.8;

/** Never spin: a server that answered with a tiny expiry must not be hammered. */
const MIN_REFRESH_MS = 5_000;

/** How close to expiry counts as "renew now" when the tab comes back. */
const WAKE_MARGIN_MS = 30_000;

/** Backoff for a renewal that failed while the book is still open. */
const RETRY_DELAYS_MS = [1_000, 2_000, 5_000, 15_000, 30_000];

type ReaderSessionStatus = 'pending' | 'ready' | 'error';

export interface ReaderSession {
  status: ReaderSessionStatus;
  /** True only while a cookie that has actually lapsed is being replaced. */
  isRenewing: boolean;
}

const refreshDelayMs = (expiresIn: number) =>
  Math.max(expiresIn * 1000 * REFRESH_AT, MIN_REFRESH_MS);

/** One book's publication cookie, minted on open and re-minted before it lapses. */
export const useReaderSession = (bookId: number): ReaderSession => {
  const [status, setStatus] = useState<ReaderSessionStatus>('pending');
  const [isRenewing, setIsRenewing] = useState(false);
  // Null until a cookie has ever been issued, which is what separates "this
  // reader never started" from "a renewal went wrong mid-book".
  const expiresAtRef = useRef<number | null>(null);
  const failuresRef = useRef(0);

  useEffect(() => {
    // Read through a call, never the flag itself: assignments from the cleanup
    // are invisible to the compiler, which would prove the checks redundant.
    const teardown = new AbortController();
    const isStale = () => teardown.signal.aborted;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = (delay: number) => {
      clearTimeout(timer);
      timer = setTimeout(() => void mintCookie(), delay);
    };

    const mintCookie = async () => {
      if (isStale() || inFlight) return;
      inFlight = true;
      try {
        const session = await startPublicationSession(bookId);
        if (isStale()) return;
        failuresRef.current = 0;
        expiresAtRef.current = Date.now() + session.expires_in * 1000;
        setIsRenewing(false);
        setStatus('ready');
        schedule(refreshDelayMs(session.expires_in));
      } catch {
        if (isStale()) return;
        // Never having held a cookie is fatal: nothing can load without one.
        if (expiresAtRef.current === null) {
          setStatus('error');
          return;
        }
        // Losing a renewal is not: the cookie in the browser may still be good
        // and the reader mid-page, so a blip must not cost them their place.
        const delay = RETRY_DELAYS_MS[Math.min(failuresRef.current, RETRY_DELAYS_MS.length - 1)];
        failuresRef.current += 1;
        schedule(delay);
      } finally {
        inFlight = false;
      }
    };

    // A backgrounded tab has its timers throttled to minutes and a sleeping
    // machine runs none, so the renewal can land long after the cookie died.
    const renewIfDue = () => {
      if (isStale() || document.visibilityState !== 'visible') return;
      const expiresAt = expiresAtRef.current;
      if (expiresAt === null || Date.now() <= expiresAt - WAKE_MARGIN_MS) return;
      // A cookie that has actually run out leaves the navigator loading against
      // a dead credential; one renewed early needs no such ceremony.
      if (Date.now() >= expiresAt) setIsRenewing(true);
      void mintCookie();
    };

    void mintCookie();
    document.addEventListener('visibilitychange', renewIfDue);
    window.addEventListener('focus', renewIfDue);

    return () => {
      teardown.abort();
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', renewIfDue);
      window.removeEventListener('focus', renewIfDue);
    };
  }, [bookId]);

  return { status, isRenewing };
};
