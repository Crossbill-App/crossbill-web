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

/**
 * How often a reader who is not turning pages says they are still here.
 *
 * Without it, two things go unrecorded. A reader who stays on one page for
 * half an hour reports nothing in that time, so the server -- which ends a
 * session by simply not being told about it again -- closes theirs at the last
 * page turn and never hears about the half hour. And a reader who opens a book
 * and reads the first page without ever turning it records no session at all,
 * because the position the book opened at is deliberately not written.
 *
 * A third of the server's idle window (30 minutes, `WEB_READING_SESSION_IDLE_
 * SECONDS`), which leaves room for two to be missed to a throttled or sleeping
 * tab before a sitting is cut in two. Being wrong here is cheap in both
 * directions: too slow splits one sitting into two, too fast costs a request
 * every few minutes.
 */
const HEARTBEAT_MS = 10 * 60 * 1000;

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
 * **A reader who is not turning pages still counts.** Every `HEARTBEAT_MS`,
 * while the tab is visible, the current position is written again unchanged --
 * which the server reads as the session continuing, because what ends a session
 * there is nothing arriving rather than anything being said.
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

  // When anything was last said about this book, so the heartbeat below can ask
  // how long the reader has been quiet rather than counting from its own last
  // tick. Set when the book opens, so opening one does not immediately beat.
  const spokeAtRef = useRef(0);

  const send = useCallback(
    (body: ReadingPositionUpdate, viaFetch: boolean) => {
      readingRef.current = true;
      spokeAtRef.current = Date.now();
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
    // Polled rather than scheduled from each write: a timer set for one moment
    // is a promise a browser does not keep — a backgrounded tab has them
    // throttled to minutes and a sleeping machine does not run them at all — so
    // the question is asked against the clock instead, the way the publication
    // cookie's renewal is. Twice as often as a beat is due, so a tick lost to
    // throttling still leaves the next one comfortably inside the server's idle
    // window.
    const tick = setInterval(() => {
      // A backgrounded tab is not a reader: a session must not be extended for
      // a book nobody is looking at.
      if (document.visibilityState !== 'visible') return;
      const locator = latestRef.current;
      if (!locator) return;
      if (Date.now() - spokeAtRef.current < HEARTBEAT_MS) return;
      send(update(locator, new Date().toISOString(), false), false);
    }, HEARTBEAT_MS / 2);

    const flushIfHidden = () => {
      // Send what is pending, but leave the session open: coming back to the
      // tab is the same sitting.
      if (document.visibilityState === 'hidden') flush(false);
    };
    document.addEventListener('visibilitychange', flushIfHidden);
    return () => {
      document.removeEventListener('visibilitychange', flushIfHidden);
      clearInterval(tick);
      flush(true);
    };
  }, [flush, send]);

  return useCallback(
    (locator: Locator) => {
      const serialized = locator.serialize() as LocatorSchema;
      const key = JSON.stringify(serialized);
      // The place the reader was already in when the book opened. Remembering
      // it is what makes every later report a move rather than a repetition.
      if (writtenRef.current === null) {
        writtenRef.current = key;
        latestRef.current = serialized;
        // Nothing is written for merely opening a book, but staying in one is
        // reading: the heartbeat's clock starts here, so a reader settled on
        // this page is recorded even though they never turn it.
        spokeAtRef.current = Date.now();
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
