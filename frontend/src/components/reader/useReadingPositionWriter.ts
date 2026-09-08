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

/** A position, and when the reader was seen at it. */
interface Observation {
  locator: LocatorSchema;
  at: string;
}

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
 * **Nothing the book says while it is arriving is a move.** `setArriving`
 * brackets the boot, and every position reported inside it — the place the
 * navigator was told to open at, the place the frame really settled on once it
 * had laid the columns out, and whatever the resize on the way past reports —
 * is the book appearing rather than a reader going anywhere. Nobody has turned
 * a page in a book that is not on screen yet.
 *
 * This is what makes resuming safe (M2.4). A book opened at a stored position
 * reports it once as asked for and again as rendered, and those are two
 * different locators for one place; written back, they would start a reading
 * session for opening a book and rewrite the position that had just been
 * restored. The bracket is deliberately drawn around *time* rather than around
 * the restored locator: a hold that asked "is this still the place we restored
 * to" has to answer with some notion of sameness, and every such notion is
 * wrong somewhere — keyed on the position number it swallows a reader turning
 * pages through a long chapter, since a position is a span of the resource and
 * not a rendered page. Once the book has arrived, every report is the reader's.
 *
 * **A position that has not moved is not written.** A preference change, a
 * resize and a re-render all re-announce the same place.
 *
 * **A reader who is not turning pages still counts.** Every `HEARTBEAT_MS`,
 * while the tab is visible, the current position is written again unchanged --
 * which the server reads as the session continuing, because what ends a session
 * there is nothing arriving rather than anything being said.
 *
 * That applies to a reader who was *put back* somewhere just as it does to one
 * who opened at the beginning, and deliberately: dwelling is reading, arriving
 * is not. Somebody resumed onto page 200 who reads that page for ten minutes
 * has read for ten minutes, exactly as somebody who opens a new book and reads
 * its first page for ten minutes has — and suppressing the heartbeat after a
 * restore would record the second and not the first. So the invariant a resume
 * keeps is that a restore *alone* writes nothing; a restore plus ten minutes of
 * reading writes, because of the reading.
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
  // The most recent position and *when the reader was at it* — what a departing
  // write and every heartbeat send. The moment is the observation's own, never
  // the moment of sending: it is what tells the server whether this write has
  // anything new to say about where the reader is.
  const latestRef = useRef<Observation | null>(null);
  // A move that is still waiting out the debounce.
  const pendingRef = useRef<Observation | null>(null);
  // Whether a session has been started at all, so that opening a book and
  // leaving it does not close a session that was never opened.
  const readingRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // When anything was last said about this book, so the heartbeat below can ask
  // how long the reader has been quiet rather than counting from its own last
  // tick. Set when the book opens, so opening one does not immediately beat.
  const spokeAtRef = useRef(0);

  // Whether the book is still being built. Starts true, because a navigator
  // reports where it is before anybody can have read anything, and is set from
  // the boot rather than inferred from what arrives.
  //
  // A ref written by a stable callback rather than a prop: the recording
  // callback below is bound to the navigator at construction, so it must keep
  // its identity for the reader's whole life, and a render is not something the
  // boot can wait for -- the settle report follows the layout by microtasks.
  const arrivingRef = useRef(true);
  const setArriving = useCallback((arriving: boolean) => {
    arrivingRef.current = arriving;
  }, []);

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
        const observed = pending ?? latestRef.current;
        // Something to record, or a session open that needs ending. A book
        // opened and closed again without being read is neither.
        if (!observed || !(pending || readingRef.current)) return;
        send(update(observed.locator, observed.at, true), true);
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
      const observed = latestRef.current;
      if (!observed) return;
      if (Date.now() - spokeAtRef.current < HEARTBEAT_MS) return;
      // The observation's own moment, not this one: a heartbeat says the reader
      // is still here, never that they have moved. Sent with a fresh timestamp
      // it would claim to be a newer sighting than the page another tab is
      // actually on, and drag the stored position back to this one.
      send(update(observed.locator, observed.at, false), false);
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

  const record = useCallback(
    (locator: Locator) => {
      const serialized = locator.serialize() as LocatorSchema;
      const key = JSON.stringify(serialized);
      const observed: Observation = { locator: serialized, at: new Date().toISOString() };

      // The book is still arriving, or this is the very first thing said about
      // it. Either way it is where the reader already was rather than somewhere
      // they went, so it is remembered and not written. `writtenRef` is kept as
      // its own condition rather than folded into the bracket: that a book's
      // opening position is never written is an invariant of this hook, and it
      // should not depend on a caller remembering to say when a boot began.
      if (arrivingRef.current || writtenRef.current === null) {
        writtenRef.current = key;
        latestRef.current = observed;
        // Nothing is written for merely opening a book, but staying in one is
        // reading: the heartbeat's clock starts here, so a reader settled on
        // this page is recorded even though they never turn it.
        spokeAtRef.current = Date.now();
        return;
      }
      if (key === writtenRef.current) return;

      writtenRef.current = key;
      latestRef.current = observed;
      pendingRef.current = observed;
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        const pending = pendingRef.current;
        pendingRef.current = null;
        if (pending) send(update(pending.locator, pending.at, false), false);
      }, WRITE_DEBOUNCE_MS);
    },
    [send]
  );

  return { record, setArriving };
};
