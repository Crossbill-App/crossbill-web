import { startPublicationSession } from '@/api/generated/readium/readium.ts';
import { useEffect, useState } from 'react';

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

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const mintCookie = async () => {
      try {
        const session = await startPublicationSession(bookId);
        if (cancelled) return;
        setStatus('ready');
        timer = setTimeout(() => void mintCookie(), refreshDelayMs(session.expires_in));
      } catch {
        if (cancelled) return;
        setStatus('error');
      }
    };

    void mintCookie();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [bookId]);

  return status;
};
