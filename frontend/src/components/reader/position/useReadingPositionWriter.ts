/**
 * Writes down where the reader is in one book while the reader is open.
 *
 * Hand `seed` every place the book reports while it is still coming up, and
 * `moved` every place it reports afterwards, and it decides what is worth
 * sending. A failed write is swallowed: the reader is reading, the next page
 * turn tries again, and the position lost by saying nothing is the one still in
 * front of them.
 *
 * Nothing here resets when `bookId` changes: the shell is keyed by book, so a
 * different book is a different component with its own state.
 */
import type { BrowserLocatorSchema, ReadingPositionUpdate } from '@/api/generated/model';
import { putReadingPosition } from '@/api/generated/readium/readium.ts';
import { getAccessToken } from '@/api/token-manager.ts';
import { toBrowserLocator } from '@/components/reader/api/apiLocators.ts';
import { readingPositionUrl } from '@/components/reader/api/readiumUrls.ts';
import type { EbookLocation } from '@/components/reader/engine/EbookReader.ts';
import { useCallback, useEffect, useRef } from 'react';

// A page turn is not a decision to stop reading, and someone flicking through a
// chapter would otherwise write a position per page.
const WRITE_DEBOUNCE_MS = 5_000;

// A third of the server's 30-minute idle window, so two beats can be lost to a
// throttled or sleeping tab before one sitting is recorded as two.
const HEARTBEAT_MS = 10 * 60 * 1000;

/** A position, and when the reader was seen at it. */
interface Observation {
  locator: BrowserLocatorSchema;
  at: string;
}

const update = ({ locator, at }: Observation, closing: boolean): ReadingPositionUpdate => ({
  locator,
  recorded_at: at,
  closing,
});

/** Where the reader has got to in one book, written down as they go. */
export const useReadingPositionWriter = (bookId: number) => {
  // What the server is believed to hold, as its own JSON, so that "has this
  // moved" is one comparison rather than a tour of the locator's optional fields.
  const writtenRef = useRef<string | null>(null);
  // The latest position and *when the reader was at it* — what a departing
  // write and every heartbeat send.
  const latestRef = useRef<Observation | null>(null);
  // A move that is still waiting out the debounce.
  const pendingRef = useRef<Observation | null>(null);
  // Whether a session has been started at all, so that opening a book and
  // leaving it does not close a session that was never opened.
  const readingRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // When anything was last said about this book, so the heartbeat can ask how
  // long the reader has been quiet rather than counting from its own last tick.
  const spokeAtRef = useRef(0);

  const send = useCallback(
    (body: ReadingPositionUpdate, departing: boolean) => {
      readingRef.current = true;
      spokeAtRef.current = Date.now();
      if (!departing) {
        void putReadingPosition(bookId, body).catch(() => undefined);
        return;
      }
      // `keepalive` is the only kind of request a page is allowed to leave
      // behind, and the route is Bearer-only, so the token goes on by hand.
      const token = getAccessToken();
      void fetch(readingPositionUrl(bookId), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify(body),
        keepalive: true,
      }).catch(() => undefined);
    },
    [bookId]
  );

  const sendPending = useCallback(
    (departing: boolean) => {
      clearTimeout(timerRef.current);
      const pending = pendingRef.current;
      pendingRef.current = null;
      if (pending) send(update(pending, false), departing);
    },
    [send]
  );

  const close = useCallback(() => {
    clearTimeout(timerRef.current);
    const pending = pendingRef.current;
    pendingRef.current = null;
    const observed = pending ?? latestRef.current;
    // Something to record, or a session open that needs ending. A book opened
    // and closed again without being read is neither.
    if (!observed || !(pending || readingRef.current)) return;
    send(update(observed, true), true);
  }, [send]);

  useEffect(() => {
    // Polled rather than scheduled from each write: a backgrounded tab throttles
    // its timers to minutes and a sleeping machine runs none.
    const tick = setInterval(() => {
      // A backgrounded tab is not a reader: a session must not be extended for
      // a book nobody is looking at.
      if (document.visibilityState !== 'visible') return;
      const observed = latestRef.current;
      if (!observed || Date.now() - spokeAtRef.current < HEARTBEAT_MS) return;
      // A move still waiting out the debounce is what this beat has to say, so
      // it is sent as the beat rather than again a moment later.
      if (pendingRef.current) {
        sendPending(false);
        return;
      }
      // The observation's own moment, not this one: a heartbeat says the reader
      // is still here, never that they moved. A fresh timestamp would claim to
      // be a newer sighting than the page another tab is actually on.
      send(update(observed, false), false);
    }, HEARTBEAT_MS / 2);

    // Coming back to a hidden tab is the same sitting, so it flushes what is
    // pending and leaves the session open.
    const flushIfHidden = () => {
      if (document.visibilityState === 'hidden') sendPending(true);
    };
    document.addEventListener('visibilitychange', flushIfHidden);
    return () => {
      document.removeEventListener('visibilitychange', flushIfHidden);
      clearInterval(tick);
      close();
    };
  }, [send, sendPending, close]);

  /** Where the reader already is: remembered, written down nowhere. */
  const seed = useCallback((location: EbookLocation) => {
    const locator = toBrowserLocator(location);
    writtenRef.current = JSON.stringify(locator);
    latestRef.current = { locator, at: new Date().toISOString() };
    // Nothing is written for opening a book, but staying in one is reading:
    // the heartbeat's clock starts here.
    spokeAtRef.current = Date.now();
  }, []);

  /** Where the reader has moved to: written down once the moving stops. */
  const moved = useCallback(
    (location: EbookLocation) => {
      // A move reported before any seed is where the reader already was, not a move.
      if (writtenRef.current === null) {
        seed(location);
        return;
      }
      const locator = toBrowserLocator(location);
      const key = JSON.stringify(locator);
      if (key === writtenRef.current) return;

      const observed: Observation = { locator, at: new Date().toISOString() };
      writtenRef.current = key;
      latestRef.current = observed;
      pendingRef.current = observed;
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => sendPending(false), WRITE_DEBOUNCE_MS);
    },
    [seed, sendPending]
  );

  return { seed, moved };
};
