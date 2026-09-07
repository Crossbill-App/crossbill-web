import { startPublicationSession } from '@/api/generated/readium/readium.ts';
import { useEffect, useRef, useState } from 'react';

/**
 * How much of the cookie's life to spend before minting a new one.
 *
 * The cookie is httpOnly, so the page cannot see it expire — it only knows the
 * `expires_in` it was told. Renewing at four fifths leaves a real margin for a
 * slow round trip without re-posting so often that the ceiling (the access
 * token's own remaining life, ADR-0004 Amendment 1) is hit every time.
 */
const REFRESH_AT = 0.8;

/** Never spin: a server that answered with a tiny expiry must not be hammered. */
const MIN_REFRESH_MS = 5_000;

/**
 * How close to expiry counts as "renew now" when the tab comes back.
 *
 * Wide enough to cover a slow round trip, so a reader who returns to the tab
 * turns a page against a cookie that is still good rather than one that dies
 * mid-request.
 */
const WAKE_MARGIN_MS = 30_000;

/** Backoff for a renewal that failed while the book is still open. */
const RETRY_DELAYS_MS = [1_000, 2_000, 5_000, 15_000, 30_000];

export type ReaderSessionStatus = 'pending' | 'ready' | 'error';

const refreshDelayMs = (expiresIn: number) =>
  Math.max(expiresIn * 1000 * REFRESH_AT, MIN_REFRESH_MS);

/**
 * Keeps a publication cookie alive for one book while the reader is open.
 *
 * The navigator loads a book's resources into iframes, and an iframe load
 * carries cookies and nothing else — never the in-memory access token. This
 * hook is what buys that second credential: it POSTs the session endpoint with
 * the Bearer token the axios instance already attaches, and re-posts on a
 * timer derived from the `expires_in` it answers with.
 *
 * A 401 on the POST is not handled here. The axios interceptor refreshes the
 * access token and replays the request, and only a genuinely dead session
 * falls through it — into the same redirect to the login page every other call
 * in the app takes.
 *
 * The status is not reset when `bookId` changes: the reader is mounted with
 * the book's id as its key, so a different book is a different component with
 * its own state rather than this one being asked to change books underneath
 * itself.
 */
export const useReaderSession = (bookId: number): ReaderSessionStatus => {
  const [status, setStatus] = useState<ReaderSessionStatus>('pending');
  // When the cookie the server last handed out runs out, in wall-clock terms.
  // Null until one has ever been issued, which is what separates "this reader
  // never started" from "a renewal went wrong mid-book".
  const expiresAtRef = useRef<number | null>(null);
  const failuresRef = useRef(0);

  useEffect(() => {
    // Read through a call, never the flag itself: assignments from the cleanup
    // below are invisible to the compiler, which would then prove the checks
    // after each await redundant.
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
        setStatus('ready');
        schedule(refreshDelayMs(session.expires_in));
      } catch {
        if (isStale()) return;
        // Never having held a cookie is fatal: nothing can load without one.
        if (expiresAtRef.current === null) {
          setStatus('error');
          return;
        }
        // Losing a *renewal* is not. The cookie in the browser may still be
        // good, the reader is mid-page, and the usual cause is a blip that
        // will have passed by the next attempt. Ending the session here would
        // tear down the navigator and lose their place over a dropped packet.
        const delay = RETRY_DELAYS_MS[Math.min(failuresRef.current, RETRY_DELAYS_MS.length - 1)];
        failuresRef.current += 1;
        schedule(delay);
      } finally {
        inFlight = false;
      }
    };

    /**
     * Timers are not a promise the browser keeps. A backgrounded tab has them
     * throttled to minutes, and a sleeping machine does not run them at all,
     * so the renewal scheduled comfortably inside the cookie's life can land
     * long after it expired. Whenever the reader comes back to the tab, the
     * question is asked against the clock instead.
     */
    const renewIfDue = () => {
      if (isStale() || document.visibilityState !== 'visible') return;
      const expiresAt = expiresAtRef.current;
      if (expiresAt !== null && Date.now() > expiresAt - WAKE_MARGIN_MS) void mintCookie();
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

  return status;
};
