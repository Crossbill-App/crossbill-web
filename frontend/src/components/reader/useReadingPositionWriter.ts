import { API_BASE_URL } from '@/api/base-url.ts';
import type { LocatorSchema, ReadingPositionUpdate } from '@/api/generated/model';
import { putReadingPosition } from '@/api/generated/readium/readium.ts';
import type { Locator } from '@readium/shared';
import { useCallback, useEffect, useRef } from 'react';

/**
 * How long the reader has to settle before their place is written down.
 *
 * A page turn is not a decision to stop reading, and someone flicking through
 * a chapter would otherwise write a position per page. Long enough to collapse
 * a run of turns into one write; short enough that a tab killed outright loses
 * only a few pages, since the flush below cannot run when the browser gives the
 * page no chance to.
 */
const WRITE_DEBOUNCE_MS = 5_000;

const positionUrl = (bookId: number) =>
  new URL(`${API_BASE_URL}/api/v1/readium/books/${bookId}/reading-position`, window.location.origin)
    .href;

const update = (locator: LocatorSchema, at: string, closing: boolean): ReadingPositionUpdate => ({
  locator,
  recorded_at: at,
  closing,
});

/**
 * Records where the reader is, debounced, and makes sure the last one lands.
 *
 * Returns one function: hand it every locator the navigator reports and it
 * decides what is worth writing.
 *
 * **The first position is remembered, not written.** The navigator announces
 * where it is as soon as a frame loads, so opening a book reports a position
 * before any reading has happened. Writing that would start a reading session
 * for merely opening a book — and, once M2.4 resumes into a stored position,
 * would write back the very position it had just restored.
 *
 * **A position that has not moved is not written.** A preference change, a
 * resize and a re-render all re-announce the same place.
 *
 * **Leaving closes the session; going to another tab does not.** Unmounting
 * writes the last position with `closing`, which is what ends the reading
 * session the server has been extending — and it writes even when nothing is
 * pending, because a session that stopped being extended without being closed
 * would be picked up again by the next sitting inside the idle timeout. A tab
 * merely hidden flushes only what is pending and leaves the session open, since
 * coming back to it is the same sitting.
 *
 * Both of those go out through `fetch` with `keepalive`, the only kind of
 * request a page is allowed to leave behind; axios can promise nothing once the
 * document is going away. The publication cookie rides along on `credentials`
 * and the endpoint takes it (ADR-0004, Amendment 1), so a departing write needs
 * no access token in a header it may have no opportunity to set.
 */
export const useReadingPositionWriter = (bookId: number) => {
  // What the server is believed to hold, as its own JSON, so that "has this
  // moved" is one comparison rather than a tour of the locator's optional
  // fields. Seeded by the position the book opened at.
  const writtenRef = useRef<string | null>(null);
  // The most recent position, written or not — what a departing write sends.
  const latestRef = useRef<LocatorSchema | null>(null);
  // A move that is still waiting out the debounce.
  const pendingRef = useRef<{ locator: LocatorSchema; at: string } | null>(null);
  // Whether a session has been started at all, so that opening a book and
  // leaving it does not close a session that was never opened.
  const readingRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const send = useCallback(
    (body: ReadingPositionUpdate, viaFetch: boolean) => {
      readingRef.current = true;
      // A failed write is not worth telling the reader about: they are reading,
      // the next page turn tries again, and the position lost by saying nothing
      // is the one still in front of them.
      if (!viaFetch) {
        void putReadingPosition(bookId, body).catch(() => undefined);
        return;
      }
      void fetch(positionUrl(bookId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'include',
        keepalive: true,
      }).catch(() => undefined);
    },
    [bookId]
  );

  const flush = useCallback(
    (closing: boolean) => {
      clearTimeout(timerRef.current);
      const pending = pendingRef.current;
      pendingRef.current = null;
      if (closing) {
        const locator = pending?.locator ?? latestRef.current;
        // Something to record, or a session open that needs ending. A book
        // opened and closed again without being read is neither.
        if (!locator || !(pending || readingRef.current)) return;
        send(update(locator, new Date().toISOString(), true), true);
        return;
      }
      if (pending) send(update(pending.locator, pending.at, false), true);
    },
    [send]
  );

  useEffect(() => {
    const flushIfHidden = () => {
      if (document.visibilityState === 'hidden') flush(false);
    };
    document.addEventListener('visibilitychange', flushIfHidden);
    return () => {
      document.removeEventListener('visibilitychange', flushIfHidden);
      flush(true);
    };
  }, [flush]);

  return useCallback(
    (locator: Locator) => {
      const serialized = locator.serialize() as LocatorSchema;
      const key = JSON.stringify(serialized);
      // The place the reader was already in when the book opened. Remembering
      // it is what makes every later report a move rather than a repetition.
      if (writtenRef.current === null) {
        writtenRef.current = key;
        latestRef.current = serialized;
        return;
      }
      if (key === writtenRef.current) return;

      writtenRef.current = key;
      latestRef.current = serialized;
      pendingRef.current = { locator: serialized, at: new Date().toISOString() };
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        const pending = pendingRef.current;
        pendingRef.current = null;
        if (pending) send(update(pending.locator, pending.at, false), false);
      }, WRITE_DEBOUNCE_MS);
    },
    [send]
  );
};
