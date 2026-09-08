import type { Highlight, HighlightLocatorResponse } from '@/api/generated/model';
import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { aManifest, aResumePosition } from '@tests/fixtures/publication';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import {
  DENSE_CHAPTER_TEXT,
  ESCAPE_HATCH,
  noPublication,
  readingPositionApi,
  readiumApi,
  sessionUnauthorizedOnce,
} from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, expect, test, vi } from 'vitest';
import { page, userEvent } from 'vitest/browser';

/** Narrower than the `sm` breakpoint the reader lays itself out against. */
const PHONE_VIEWPORT = { width: 390, height: 780 };

/** `vitest.config.ts`'s own viewport, restored after a test has narrowed it. */
const DEFAULT_VIEWPORT = { width: 1440, height: 900 };

afterEach(async () => {
  await page.viewport(DEFAULT_VIEWPORT.width, DEFAULT_VIEWPORT.height);
});

/**
 * `bookApi` serves a book with no EPUB by default, so the reader's own
 * handlers have to be registered afterwards to win: MSW resolves in
 * registration order, newest first.
 *
 * `has_ebook` is what the book page reads to decide whether to offer the Read
 * tab; the Readium handlers are what the reader itself needs once the tab is
 * followed. A book with an EPUB has both.
 */
const aBookWithAnEpub = (...extra: Parameters<typeof worker.use>) =>
  aBookWithAPublication({}, ...extra);

/** `aBookWithAnEpub`, for a test that needs the publication served differently. */
const aBookWithAPublication = (
  publication: Parameters<typeof readiumApi>[0],
  ...extra: Parameters<typeof worker.use>
) => {
  worker.use(
    ...bookApi({ book: aBookDetails({ title: 'The Pragmatic Reader', has_ebook: true }) }).handlers
  );
  worker.use(...readiumApi(publication));
  // A separate call, so a handler a test passes in wins: MSW gives later `use`
  // calls priority, while within one call the first argument wins.
  if (extra.length) worker.use(...extra);
};

test('the reader opens with the book title and its controls', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });

  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Contents' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Appearance' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Previous page' })).toBeVisible();
});

/** The book open on a phone-sized viewport, showing its first page. */
const aBookOpenOnAPhone = async (...extra: Parameters<typeof worker.use>) => {
  aBookWithAnEpub(...extra);
  await page.viewport(PHONE_VIEWPORT.width, PHONE_VIEWPORT.height);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  return screen;
};

/**
 * On a phone the two arrow gutters were most of the screen, and the book was a
 * strip down the middle. The buttons go, and the chrome above the page — which
 * fits either way — stays exactly as it was.
 */
test('the arrow buttons give the page its width back on a phone', async () => {
  const screen = await aBookOpenOnAPhone();

  expect(screen.getByRole('button', { name: 'Next page' }).query()).toBeNull();
  expect(screen.getByRole('button', { name: 'Previous page' }).query()).toBeNull();
  await expect.element(screen.getByRole('button', { name: 'Contents' })).toBeVisible();
});

/**
 * A pointer gesture inside the publication's own frame.
 *
 * The tap zones listen in the frame rather than over it — an overlay would sit
 * between the reader and the book and eat the selection and the links that
 * belong to it — so a test has to reach into the frame the way a finger does.
 * `userEvent` cannot: it drives the page the test is rendered in, and the frame
 * is a document of its own.
 */
const gestureInPublication = async ({
  across,
  dragBy = 0,
  holdFor = 0,
  onSelection = false,
  resizeTo,
}: {
  across: number;
  dragBy?: number;
  holdFor?: number;
  onSelection?: boolean;
  /** Resize the viewport mid-gesture, as a rotation does. */
  resizeTo?: { width: number; height: number };
}) => {
  // Readium keeps a pool of frames and hides the ones that are not on screen.
  // Only the visible one is the page the reader is looking at, and only it is
  // the frame the navigator reported through `frameLoaded`.
  const frame = [
    ...document.querySelectorAll<HTMLIFrameElement>('iframe.readium-navigator-iframe'),
  ].find((candidate) => candidate.style.visibility !== 'hidden');
  const view = frame?.contentWindow as (Window & typeof globalThis) | null | undefined;
  if (!view || !frame?.contentDocument) throw new Error('The publication has no frame to tap.');

  const from = Math.round(view.innerWidth * across);
  const y = Math.round(view.innerHeight / 2);
  const target = frame.contentDocument.elementFromPoint(from, y) ?? frame.contentDocument.body;
  const at = (clientX: number) => ({
    clientX,
    clientY: y,
    bubbles: true,
    isPrimary: true,
    pointerId: 1,
    pointerType: 'touch',
  });

  if (onSelection) view.getSelection()?.selectAllChildren(frame.contentDocument.body);

  target.dispatchEvent(new view.PointerEvent('pointerdown', at(from)));
  if (dragBy !== 0) target.dispatchEvent(new view.PointerEvent('pointermove', at(from - dragBy)));
  if (holdFor !== 0) await new Promise((resolve) => setTimeout(resolve, holdFor));
  if (resizeTo) {
    await page.viewport(resizeTo.width, resizeTo.height);
    // The media query has to reach React, and React the reader, before the
    // finger comes up — otherwise the race this simulates never happens.
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  target.dispatchEvent(new view.PointerEvent('pointerup', at(from - dragBy)));
};

/** Long enough for a page turn to have landed if one was coming. */
const A_PAGE_TURN = 1_200;

/** That the reader stayed where it was, waited out long enough to mean it. */
const expectNoPageTurn = async () => {
  await new Promise((resolve) => setTimeout(resolve, A_PAGE_TURN));
  expect(document.body.innerText).toContain('Page 1 of 2');
};

test('a tap on the right of the page turns to the next one', async () => {
  const screen = await aBookOpenOnAPhone();

  await gestureInPublication({ across: 0.9 });

  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});

test('a tap on the left of the page turns back', async () => {
  aBookWithAnEpub(...readingPositionApi(aResumePosition()).handlers);
  await page.viewport(PHONE_VIEWPORT.width, PHONE_VIEWPORT.height);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();

  await gestureInPublication({ across: 0.1 });

  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
});

/**
 * The zones are the edges, not the whole page: the middle has to stay a place a
 * reader can put a finger down without losing their place.
 */
test('a tap in the middle of the page turns nothing', async () => {
  await aBookOpenOnAPhone();

  await gestureInPublication({ across: 0.5 });

  await expectNoPageTurn();
});

/**
 * A swipe, a drag across text and a flick to scroll all begin as a pointer put
 * down on the page, and every one of them would land in a tap zone. What
 * separates a tap from all of them is that the pointer did not travel.
 */
test('a pointer that travelled across the zone is not a tap', async () => {
  await aBookOpenOnAPhone();

  await gestureInPublication({ across: 0.9, dragBy: 30 });

  await expectNoPageTurn();
});

/**
 * A long press is how a reader opens a selection, and M4 will hang the
 * highlighting on it. Holding a finger down in a tap zone must not cost them
 * the page they were about to select from.
 */
test('a finger held down in the zone is not a tap', async () => {
  await aBookOpenOnAPhone();

  await gestureInPublication({ across: 0.9, holdFor: 700 });

  await expectNoPageTurn();
});

/**
 * Selecting text runs to the edge of the page like any other text, so the tap
 * that lands on a selection — and the one that dismisses it — has to leave the
 * page alone. Otherwise a reader loses the passage they had just selected.
 */
test('a tap on selected text is not a page turn', async () => {
  await aBookOpenOnAPhone();

  await gestureInPublication({ across: 0.9, onSelection: true });

  await expectNoPageTurn();
});

/**
 * The zones are physical edges, so what they mean depends on which way the book
 * runs. In an Arabic or Hebrew book the next page lies to the *left*, and a
 * reader tapping the left edge is reaching for it — the navigator's own
 * `goLeft`/`goRight` are what map an edge onto a direction.
 *
 * The progression is taken from the language here, which is how Readium derives
 * it when a manifest does not say (`Metadata.effectiveReadingProgression`), and
 * how our own manifests arrive: the backend publishes no `readingProgression`.
 * This pins the mapping only — M2.2 left RTL *rendering* untested, and this does
 * not certify it.
 */
test('a tap on the left of a right-to-left book turns forward', async () => {
  aBookWithAPublication({
    manifest: aManifest({
      metadata: { title: 'The Pragmatic Reader', language: 'ar', identifier: 'urn:uuid:rtl' },
    }),
  });
  await page.viewport(PHONE_VIEWPORT.width, PHONE_VIEWPORT.height);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await gestureInPublication({ across: 0.1 });

  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});

/**
 * A rotation can cross the breakpoint between a finger going down and coming
 * up. Sampling only at the end would let a gesture begun in button territory
 * turn a page, so both ends of the tap have to agree that taps turn pages.
 */
test('a gesture that crosses the breakpoint mid-tap turns nothing', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await gestureInPublication({ across: 0.9, resizeTo: PHONE_VIEWPORT });

  await expectNoPageTurn();
});

/** The arrow buttons are still the way to turn a page where there is room for them. */
test('a click on the edge of the page turns nothing on a desktop viewport', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await gestureInPublication({ across: 0.9 });

  await expectNoPageTurn();
});

/**
 * The one test that drives the real navigator end to end: MSW serves the
 * manifest, the position list and the chapters, and Readium does its own
 * fetching, blob-building and framing on top. It earns its keep by proving the
 * two things the spike could not — that the container is sized before the
 * frames are built, and that `frameLoaded` reaches us — so it stays.
 */
test('the book loads into the reader and it reports where it is', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });

  // The skeleton stands until the first frame is in the DOM.
  await expect.element(screen.getByLabelText('Loading the book')).not.toBeInTheDocument();
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
});

/**
 * Readium frames a publication in an iframe that is same-origin with the app
 * and carries `allow-same-origin allow-scripts`, so a book's own JavaScript
 * would run with the page's own privileges — able to read the DOM, spend the
 * session cookie, and call the API as the reader. Books here come from
 * wherever their owner found them, so "the EPUB is trusted" is not a premise
 * worth holding.
 */
test('a book cannot run its own scripts against the page that opened it', async () => {
  worker.use(...bookApi({ book: aBookDetails({ title: 'The Pragmatic Reader' }) }).handlers);
  worker.use(...readiumApi({ hostile: true }));

  // A file the publication never references, so asking for it can only mean
  // the frame navigated out of the document we sanitised and into a raw,
  // unsanitised one served straight from the API.
  let escaped = false;
  worker.use(
    http.get(`/api/v1/readium/books/:bookId/resources/OEBPS/${ESCAPE_HATCH}`, () => {
      escaped = true;
      return new HttpResponse('', { headers: { 'Content-Type': 'application/xhtml+xml' } });
    })
  );

  const screen = await renderApp({ path: '/book/1/read' });

  // Settled rather than polled: a script that got through would mark the page
  // a frame or two after the chapter renders, so an immediate assertion could
  // pass while the attack was still in flight. Long enough, too, for a meta
  // refresh to navigate the frame.
  await new Promise((resolve) => setTimeout(resolve, 1500));
  expect(document.body.getAttribute('data-pwned')).toBeNull();
  expect(escaped).toBe(false);

  // And the book really did render, so the assertions above were about a
  // loaded chapter rather than an empty frame that could never attack anything.
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
});

test('the contents drawer lists the chapters the manifest publishes', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });
  await screen.getByRole('button', { name: 'Contents' }).click();

  const contents = screen.getByRole('navigation', { name: 'Table of contents' });
  await expect.element(contents.getByText('On Attention')).toBeVisible();
  // A part heading and the chapter nested under it: the tree is kept, not flattened.
  await expect.element(contents.getByText('Part two')).toBeVisible();
  await expect.element(contents.getByText('On Memory')).toBeVisible();
});

test('the appearance popover offers font size and page colour', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });
  await screen.getByRole('button', { name: 'Appearance' }).click();

  await expect.element(screen.getByRole('slider', { name: 'Font size' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Sepia' })).toBeVisible();
  await screen.getByRole('button', { name: 'Sepia' }).click();
  await expect
    .element(screen.getByRole('button', { name: 'Sepia' }))
    .toHaveAttribute('aria-pressed', 'true');
});

/**
 * The reader listens for arrow keys on the window so the book turns wherever
 * the focus is. That used to mean the font-size slider did two things at once:
 * grew the text and skipped a page.
 */
test('an arrow key on the font-size slider does not also turn the page', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await screen.getByRole('button', { name: 'Appearance' }).click();
  const slider = screen.getByRole('slider', { name: 'Font size' });
  await expect.element(slider).toBeVisible();

  // Focused rather than clicked: this is the keyboard user's route to the
  // control, and clicking a slider thumb mid-transition is a fight with the
  // animation rather than a test of anything.
  (slider.element() as HTMLElement).focus();
  await userEvent.keyboard('{ArrowRight}');

  // The slider took the key...
  await expect.element(slider).not.toHaveAttribute('aria-valuenow', '1');

  // ...and the book stayed where it was. Settled rather than asserted straight
  // away: a page turn lands about a second later, so an immediate check would
  // pass whether or not one was on its way.
  await new Promise((resolve) => setTimeout(resolve, 1200));
  expect(document.body.innerText).toContain('Page 1 of 2');
});

/**
 * A load that fails used to leave the skeleton up forever, and — because
 * teardown was chained off the boot's success — leak the half-built
 * navigator's frames and blobs when the reader gave up and left.
 */
test('a book whose chapters will not load says so, and can be retried', async () => {
  worker.use(...bookApi({ book: aBookDetails() }).handlers);
  worker.use(...readiumApi());
  worker.use(
    http.get(
      '/api/v1/readium/books/:bookId/resources/*',
      () => new HttpResponse(null, { status: 500 })
    )
  );

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(screen.getByText('This book could not be opened in the reader.'))
    .toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Try again' })).toBeVisible();
});

/**
 * The slow one, and it earns it. A load that hangs cannot be waited out, and
 * every later step was chained to it — including the teardown, and so the next
 * attempt: "Try again" queued behind the load that hung and waited forever.
 * Nothing short of a real hang reproduces that, and a real hang means waiting
 * for the watchdog.
 */
test('a book whose load never finishes can still be retried', { timeout: 40_000 }, async () => {
  worker.use(...bookApi({ book: aBookDetails() }).handlers);
  worker.use(...readiumApi());

  let chapterRequests = 0;
  worker.use(
    http.get('/api/v1/readium/books/:bookId/resources/OEBPS/chapter1.xhtml', async () => {
      chapterRequests += 1;
      // Never settles, which is what a hung load is.
      await new Promise(() => {});
      return new HttpResponse(null);
    })
  );

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(screen.getByRole('button', { name: 'Try again' }), { timeout: 25_000 })
    .toBeVisible();
  expect(chapterRequests).toBe(1);

  await screen.getByRole('button', { name: 'Try again' }).click();

  // A second attempt at the chapter means a genuinely new navigator was built,
  // rather than one queued behind a promise that will never settle.
  await vi.waitFor(() => expect(chapterRequests).toBe(2), { timeout: 10_000 });
});

/**
 * Coming back to a tab that slept past the cookie's expiry starts a renewal,
 * but the navigator was still interactive while it ran: a page turn would ask
 * for a chapter with a dead credential and get a blank frame.
 */
test('a lapsed session holds the book until it has been renewed', async () => {
  worker.use(...bookApi({ book: aBookDetails() }).handlers);
  // One second of life, so the cookie has genuinely lapsed by the time the tab
  // is brought back. The scheduled renewal cannot interfere: its floor is five.
  worker.use(...readiumApi({ expiresIn: 1 }));

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  // The renewal that the return to the tab triggers, held open long enough to
  // observe what the reader does while it is in flight.
  worker.use(
    http.post('/api/v1/readium/books/:bookId/session', async () => {
      await delay(2_000);
      return HttpResponse.json({ expires_in: 900 });
    })
  );

  await new Promise((resolve) => setTimeout(resolve, 1_200));
  window.dispatchEvent(new Event('focus'));

  await expect.element(screen.getByText('Reconnecting...')).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();

  // ...and the book comes back on its own once the cookie has.
  await expect
    .element(screen.getByText('Reconnecting...'), { timeout: 5_000 })
    .not.toBeInTheDocument();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
});

/** A session that never succeeded is terminal — nothing can load without one. */
test('a session that cannot be started at all reports it', async () => {
  worker.use(...bookApi({ book: aBookDetails() }).handlers);
  worker.use(...readiumApi());
  worker.use(
    http.post(
      '/api/v1/readium/books/:bookId/session',
      () => new HttpResponse(null, { status: 500 })
    )
  );

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(
      screen.getByText('The reader could not start a session for this book.', { exact: false })
    )
    .toBeVisible();
});

test('closing the reader goes back to the book', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/read' });
  await screen.getByRole('button', { name: 'Close reader' }).click();

  await expect.element(screen.getByRole('heading', { name: 'Structure' })).toBeVisible();
  expect(window.location.pathname).toBe('/book/1/structure');
});

test('a book with an EPUB offers the Read tab', async () => {
  aBookWithAnEpub();

  const screen = await renderApp({ path: '/book/1/structure' });

  await expect.element(screen.getByRole('link', { name: 'Read' })).toBeVisible();
});

test('a book with no EPUB does not offer the Read tab', async () => {
  worker.use(...bookApi({ book: aBookDetails() }).handlers);

  const screen = await renderApp({ path: '/book/1/structure' });
  await expect.element(screen.getByRole('heading', { name: 'Structure' })).toBeVisible();

  await expect(screen.getByRole('link', { name: 'Read' }).query()).toBeNull();
});

test('opening the reader for a book with no EPUB explains there is nothing to read', async () => {
  worker.use(...bookApi({ book: aBookDetails() }).handlers);
  worker.use(...noPublication);

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(screen.getByText('This book has no EPUB file', { exact: false }))
    .toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Back to book' })).toBeVisible();
});

/**
 * A 401 on the session POST is not the reader's problem to solve: the shared
 * axios interceptor refreshes the access token and replays the request, which
 * is the same re-auth path every other call in the app takes. What matters
 * here is that the reader lets it happen rather than dead-ending on the 401.
 */
test('a session refused with a 401 is retried through the app refresh', async () => {
  let refreshes = 0;
  aBookWithAnEpub(
    http.post('/api/v1/auth/refresh', () => {
      refreshes += 1;
      return HttpResponse.json({
        access_token: 'fresh-token',
        refresh_token: 'fresh-refresh',
        token_type: 'bearer',
        expires_in: 900,
      });
    })
  );
  // Registered last so it answers the first session POST; the replay after the
  // refresh falls through to the handler `readiumApi` registered above.
  worker.use(sessionUnauthorizedOnce);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();

  await expect.poll(() => refreshes).toBeGreaterThan(0);
});

/**
 * The reader's place is written back so that both readers agree where it is,
 * and so that reading in the browser shows up in the reading statistics.
 *
 * The wait is the debounce, not slack: writing every page turn would be a
 * request per page, so the reader has to go quiet before its place is written.
 * These tests wait it out rather than faking the clock, because the navigator's
 * own boot is a chain of timers and animation frames — a fake clock would be
 * testing the mock's scheduler rather than the reader.
 */
test('turning a page writes the new position, once the reader settles', async () => {
  const positions = readingPositionApi();
  aBookWithAnEpub(...positions.handlers);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  // Nothing yet: where the book opened is where the reader already was.
  expect(positions.writes).toHaveLength(0);

  await screen.getByRole('button', { name: 'Next page' }).click();

  await expect.poll(() => positions.writes.length, { timeout: 15_000 }).toBe(1);
  const [write] = positions.writes;
  expect(write.locator.href).toBe('resources/OEBPS/chapter2.xhtml');
  expect(write.closing).toBe(false);
  expect(Date.parse(write.recorded_at)).toBeGreaterThan(0);
}, 30_000);

test('a reader who has not moved writes nothing at all', async () => {
  const positions = readingPositionApi();
  aBookWithAnEpub(...positions.handlers);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  // Comfortably past the debounce: a reader that wrote where the book opened,
  // or re-wrote the same place on every re-render, would have written by now.
  await new Promise((resolve) => setTimeout(resolve, 8_000));
  expect(positions.writes).toHaveLength(0);
}, 30_000);

/**
 * Leaving the reader is what ends the reading session the server has been
 * extending, so the last position must not be lost to the debounce — and it
 * must say the book is being closed, or the next sitting would be folded into
 * this one.
 */
test('closing the reader writes the last position immediately, and closes the session', async () => {
  const positions = readingPositionApi();
  aBookWithAnEpub(...positions.handlers);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  await screen.getByRole('button', { name: 'Next page' }).click();
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();

  await screen.getByRole('button', { name: 'Close reader' }).click();
  await expect.element(screen.getByRole('heading', { name: 'Structure' })).toBeVisible();

  // Well inside the debounce, so only the flush can have sent this.
  await expect.poll(() => positions.writes.length).toBeGreaterThan(0);
  const last = positions.writes[positions.writes.length - 1];
  expect(last.closing).toBe(true);
  expect(last.locator.href).toBe('resources/OEBPS/chapter2.xhtml');
}, 30_000);

/**
 * Opening a book puts the reader back where they left off — on this device or
 * another (M2.4, #743). The server answers with a locator whichever reader
 * recorded the place, so the reader here does not know or care which it was;
 * what it has to do is open the navigator *at* that place rather than at the
 * beginning, and not write it straight back as a move.
 */
test('a book opens where the reader left off', async () => {
  aBookWithAnEpub(...readingPositionApi(aResumePosition()).handlers);

  const screen = await renderApp({ path: '/book/1/read' });

  // Chapter two, which is not where this book opens on its own — so the page
  // number is the restore rather than a default.
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});

test('a place the e-reader recorded opens the same way', async () => {
  aBookWithAnEpub(...readingPositionApi(aResumePosition({ source: 'koreader' })).handlers);

  const screen = await renderApp({ path: '/book/1/read' });

  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});

/**
 * Restoring a place must not be mistaken for going somewhere. The navigator
 * reports the restored position as soon as its frame loads, and again once the
 * frame has settled into it — the same place, carrying the progression it
 * really rendered at rather than the one that was asked for. Written back, that
 * is a reading session for opening a book, and a position rewritten from a
 * reader who has not read a word.
 */
test('restoring a position writes nothing back', async () => {
  const positions = readingPositionApi(aResumePosition());
  aBookWithAnEpub(...positions.handlers);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();

  // Comfortably past the debounce, so a write the restore provoked would have
  // landed by now.
  await new Promise((resolve) => setTimeout(resolve, 8_000));
  expect(positions.writes).toHaveLength(0);
}, 30_000);

/**
 * The two halves of a place that could not be restored: the book opens anyway,
 * at its beginning, and the reader is told why it is not where they left it.
 * Asserted together because either alone is the wrong outcome — a book that
 * does not open, or one that silently loses somebody's place.
 */
const expectAStartAndAnApology = async () => {
  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  await expect
    .element(screen.getByText("Couldn't restore your last position", { exact: false }))
    .toBeVisible();
};

/**
 * The EPUB has been replaced since the place was recorded, so the xpointer that
 * still safely holds it no longer names anywhere in the book (ADR-0004 §5). The
 * server says so rather than guessing, and the reader is told — because opening
 * at page one with no explanation looks exactly like a reader who never got
 * anywhere.
 */
test('a place that could not be found says so, and the book still opens', async () => {
  aBookWithAnEpub(
    ...readingPositionApi(aResumePosition({ locator: null, source: 'koreader', unresolved: true }))
      .handlers
  );

  await expectAStartAndAnApology();
});

/**
 * The stored locator names a resource this publication no longer has. The
 * navigator would throw on it — its frame pool looks an initial position up in
 * the position list and refuses one that is not there — which would cost the
 * reader the whole book rather than a bookmark. Caught before it is offered.
 */
test('a place in a chapter the book no longer has costs a bookmark, not the book', async () => {
  aBookWithAnEpub(
    ...readingPositionApi(
      aResumePosition({
        locator: {
          href: 'resources/OEBPS/chapter9.xhtml',
          type: 'application/xhtml+xml',
          locations: { position: 9, progression: 0 },
        },
      })
    ).handlers
  );

  await expectAStartAndAnApology();
});

/**
 * A position is a span of the *resource*, not a rendered page, so a chapter
 * longer than a screen paginates into several columns that all sit inside one
 * entry of the position list. Turning a page there is unmistakably reading and
 * leaves `locations.position` exactly where it was.
 *
 * That is the case a hold keyed on the position number gets wrong: it classes
 * every one of those turns as the restore still settling, so nothing is
 * pending and nothing is written — and the reader closes the book having lost
 * the sitting and the progress both. The hold has to end when the book has
 * finished arriving, not when the position number happens to change.
 */
test('reading on within the restored position is still written', async () => {
  const positions = readingPositionApi(
    aResumePosition({
      locator: {
        href: 'resources/OEBPS/chapter1.xhtml',
        type: 'application/xhtml+xml',
        locations: { position: 1, progression: 0 },
      },
    })
  );
  aBookWithAPublication({ longFirstChapter: true }, ...positions.handlers);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await screen.getByRole('button', { name: 'Next page' }).click();

  // Still the same position — the turn stayed inside the long first chapter —
  // and still a page the reader turned.
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  await expect.poll(() => positions.writes.length, { timeout: 15_000 }).toBeGreaterThan(0);
  expect(positions.writes[0].locator.href).toBe('resources/OEBPS/chapter1.xhtml');
}, 30_000);

/* ------------------------------------------------------------------ *
 * M3.2 — the reader's highlights, drawn on the page (#746)
 * ------------------------------------------------------------------ */

/**
 * Two phrases of the fixture's first chapter, and the label colour each is
 * marked in.
 *
 * The chapter reads "Attention is the rarest and purest form of generosity.
 * (1)", so these are two non-overlapping quotes of one paragraph — which is
 * what makes two decorations in one frame, in two different colours, a thing a
 * test can tell apart.
 */
const FIRST_QUOTE = 'Attention is the rarest';
const SECOND_QUOTE = 'form of generosity';

/** Yellow and Blue of `LABEL_COLORS`, at the alpha the reader lays them on with. */
const YELLOW_TINT = 'rgba(245, 158, 11, 0.35)';
const BLUE_TINT = 'rgba(59, 130, 246, 0.35)';

/** The Gray a highlight whose label carries no colour falls back to. */
const DEFAULT_TINT = 'rgba(107, 114, 128, 0.35)';

const CHAPTER_ONE = 'resources/OEBPS/chapter1.xhtml';

/** A highlight of the book, marked in `uiColor` and quoting `text`. */
const aMarkedHighlight = (id: number, text: string, uiColor: string | null) =>
  aHighlight({
    id,
    text,
    label:
      uiColor === null ? null : { highlight_style_id: id, text: 'Key idea', ui_color: uiColor },
  });

/** Where that highlight is, as the reader's locator endpoint answers it. */
const aPlacedLocator = (id: number, quote: string): HighlightLocatorResponse => ({
  highlight_id: id,
  unavailable: null,
  locator: {
    href: CHAPTER_ONE,
    type: 'application/xhtml+xml',
    locations: {},
    text: { highlight: quote },
  },
});

/**
 * A book whose highlights the reader can draw: the rows in book details, the
 * places in the locator endpoint.
 *
 * The split is the production one. A highlight's label — and so its colour —
 * rides on the book-details payload the reader already fetches for the title,
 * and only where it is in the EPUB comes from the web reader's own endpoint.
 */
const aBookWithHighlights = (
  highlights: Highlight[],
  highlightLocators: HighlightLocatorResponse[],
  publication: Omit<Parameters<typeof readiumApi>[0], 'highlightLocators'> = {},
  ...extra: Parameters<typeof worker.use>
) => {
  const { handlers, state } = bookApi({
    book: aBookDetails({
      title: 'The Pragmatic Reader',
      has_ebook: true,
      chapters: [aChapter({ highlights })],
    }),
  });
  worker.use(...handlers);
  worker.use(...readiumApi({ ...publication, highlightLocators }));
  if (extra.length) worker.use(...extra);
  return state;
};

/** The publication frame the reader is actually looking at. */
const visibleFrame = () =>
  [...document.querySelectorAll<HTMLIFrameElement>('iframe.readium-navigator-iframe')].find(
    (candidate) => candidate.style.visibility !== 'hidden'
  );

/**
 * Every colour a decoration is painted in inside the visible frame.
 *
 * Readium draws a highlight one of two ways, and which one it picks is the
 * engine's business rather than ours: where the CSS Custom Highlight API is
 * available it registers ranges and writes `::highlight()` rules into a style
 * element, and where it is not it lays absolutely positioned boxes into a
 * shadow root. Both are read here so the assertions below are about what the
 * reader sees rather than about which path this browser took.
 */
const decorationTints = (): string[] => {
  const doc = visibleFrame()?.contentDocument;
  if (!doc) return [];
  const fromRules = [...doc.querySelectorAll('style')]
    .flatMap((sheet) => [...sheet.textContent.matchAll(/::highlight\([^)]*\)\s*{[^}]*}/g)])
    .flatMap((rule) => [...rule[0].matchAll(/background-color:\s*([^;\n]+)/g)])
    .map((match) => match[1].trim());
  const fromBoxes = [...doc.querySelectorAll<HTMLElement>('div')]
    .flatMap((host) =>
      host.shadowRoot ? [...host.shadowRoot.querySelectorAll<HTMLElement>('*')] : []
    )
    .map((box) => box.style.backgroundColor)
    .filter(Boolean);
  return [...fromRules, ...fromBoxes];
};

/**
 * The tints on the page, once they have had a chance to arrive.
 *
 * Polled well past the default second, because the whole point of this layer is
 * that decorations are allowed to be late: one test below holds the locator
 * response back on purpose, and a matcher that gave up first would be asserting
 * the opposite of what the code promises.
 */
const DECORATIONS_ARRIVE_WITHIN = 6_000;

const tintsOnThePage = () =>
  expect.poll(() => [...new Set(decorationTints())].sort(), {
    timeout: DECORATIONS_ARRIVE_WITHIN,
  });

/**
 * The reader's highlights are the whole point of the milestone: a KOReader
 * highlight made months ago on a device, drawn in the browser on the words it
 * was made on, in the colour the reader chose for it.
 */
test('a book is opened with its highlights drawn on the page', async () => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, '#F59E0B'), aMarkedHighlight(302, SECOND_QUOTE, '#3B82F6')],
    [aPlacedLocator(301, FIRST_QUOTE), aPlacedLocator(302, SECOND_QUOTE)]
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await tintsOnThePage().toEqual([BLUE_TINT, YELLOW_TINT].sort());
});

/**
 * A highlight KOReader never gave a colour to is still a highlight, and still
 * has to be findable on the page — in the palette's quietest member rather than
 * in no colour at all.
 */
test('a highlight with no label colour is drawn in the default one', async () => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, null)],
    [aPlacedLocator(301, FIRST_QUOTE)]
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await tintsOnThePage().toEqual([DEFAULT_TINT]);
});

/**
 * The other half of ADR-0004 §5: a highlight the server would not place is one
 * the reader must not draw, because the only alternative to no decoration is a
 * confident one in the wrong paragraph. Saying so belongs in the chrome (M3.4),
 * not on the page.
 */
test('a highlight that could not be placed is not drawn at all', async () => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, '#F59E0B'), aMarkedHighlight(302, SECOND_QUOTE, '#3B82F6')],
    [
      aPlacedLocator(301, FIRST_QUOTE),
      { highlight_id: 302, locator: null, unavailable: 'unresolved' },
    ]
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await tintsOnThePage().toEqual([YELLOW_TINT]);
});

/** A book nobody has marked opens as a book, with nothing drawn and nothing amiss. */
test('a book with no highlights opens cleanly', async () => {
  aBookWithHighlights([], []);

  const screen = await renderApp({ path: '/book/1/read' });

  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();
  expect(decorationTints()).toEqual([]);
});

/**
 * *Amendment 5* measured a book's whole conversion at 561 ms in the worst case
 * measured, and reasons that a flat book with hundreds of highlights runs into
 * seconds. So the one thing the decorations may never do is hold up the book:
 * the text arrives first and the marks catch up.
 */
test('the book is on screen before its highlights have been placed', async () => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, '#F59E0B')],
    [],
    {},
    http.get('/api/v1/books/:bookId/highlight-locators', async () => {
      await delay(1_500);
      return HttpResponse.json({ items: [aPlacedLocator(301, FIRST_QUOTE)] });
    })
  );

  const screen = await renderApp({ path: '/book/1/read' });

  // The skeleton has cleared and the reader is reading, with the locator
  // request still in flight.
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  expect(decorationTints()).toEqual([]);

  // And the marks land on the page they belong to without it being reloaded.
  await tintsOnThePage().toEqual([YELLOW_TINT]);
});

/** One drawn highlight, tapped, with its dialog open on the book. */
const aTappedHighlight = async () => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, '#F59E0B')],
    [aPlacedLocator(301, FIRST_QUOTE)]
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await tintsOnThePage().toEqual([YELLOW_TINT]);
  await tapQuoteInPublication(FIRST_QUOTE);
  await expect.element(screen.getByRole('dialog')).toBeVisible();
  return screen;
};

/**
 * A highlight tapped in the book opens the same dialog the book page opens,
 * through the same search param — so the URL can be pasted to somebody else.
 */
test('tapping a highlight on the page opens it', async () => {
  const screen = await aTappedHighlight();

  await expect.element(screen.getByRole('dialog').getByText(FIRST_QUOTE)).toBeVisible();
  expect(window.location.search).toContain('highlightId=301');
});

/** The back button closes the dialog and leaves the reader where it was. */
test('closing a tapped highlight goes back to the book', async () => {
  const screen = await aTappedHighlight();

  window.history.back();

  await expect.poll(() => window.location.search).not.toContain('highlightId');
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
});

/** The visible frame's document and window, or a clear failure. */
const publicationFrame = () => {
  const frame = visibleFrame();
  const doc = frame?.contentDocument;
  const view = frame?.contentWindow as (Window & typeof globalThis) | null | undefined;
  if (!doc || !view) throw new Error('The publication has no frame to tap.');
  return { doc, view };
};

/** A finger down and up at one point of the publication's own document. */
const tapPoint = (
  doc: Document,
  view: Window & typeof globalThis,
  clientX: number,
  clientY: number
) => {
  const at = {
    clientX,
    clientY,
    bubbles: true,
    isPrimary: true,
    pointerId: 1,
    pointerType: 'touch',
  };
  const target = doc.elementFromPoint(clientX, clientY) ?? doc.body;
  target.dispatchEvent(new view.PointerEvent('pointerdown', at));
  target.dispatchEvent(new view.PointerEvent('pointerup', at));
};

/** The range a quote occupies in the publication's document, as Readium decorated it. */
const rangeOfQuote = (doc: Document, quote: string): Range => {
  const paragraph = [...doc.querySelectorAll('p')].find((node) => node.textContent.includes(quote));
  const textNode = paragraph?.firstChild;
  if (!textNode?.textContent) throw new Error(`No paragraph in the book quotes "${quote}".`);

  const start = textNode.textContent.indexOf(quote);
  const range = doc.createRange();
  range.setStart(textNode, start);
  range.setEnd(textNode, start + quote.length);
  return range;
};

/**
 * A finger put down on a decorated phrase, in the publication's own document.
 *
 * Readium hit-tests an activation against the rects of the decorated range, so
 * the gesture has to land on the words themselves — the range is found here the
 * same way the decoration's own was, by quote.
 */
const tapQuoteInPublication = async (quote: string) => {
  const { doc, view } = publicationFrame();
  // The first line box rather than the whole range: a quote that wraps has a
  // bounding rect spanning both lines, whose centre may be on neither.
  const box = rangeOfQuote(doc, quote).getClientRects()[0];
  tapPoint(doc, view, Math.round(box.left + box.width / 2), Math.round(box.top + box.height / 2));
};

/**
 * A tap on a highlight at a point that would otherwise turn the page.
 *
 * The point is computed from the decorated range's own line boxes rather than
 * guessed, and the search throws if no line of the highlight actually reaches
 * into the zone. Without that, a test could tap somewhere harmless and pass
 * while proving nothing — which is exactly what the first version of this did,
 * by tapping the *backward* zone on page one, where a page turn has nowhere to
 * go and leaves the readout unchanged either way.
 */
const tapHighlightInTapZone = async (quote: string, edge: 'left' | 'right') => {
  const { doc, view } = publicationFrame();
  // `TAP_ZONE_FRACTION` of `useReaderTapZones`, restated: a test that read the
  // constant from the module could not notice the module changing it.
  const zone = view.innerWidth * 0.2;
  const inZone = (x: number) => (edge === 'left' ? x < zone : x > view.innerWidth - zone);

  const point = [...rangeOfQuote(doc, quote).getClientRects()]
    .map((rect) => ({
      x: edge === 'left' ? Math.ceil(rect.left) + 2 : Math.floor(rect.right) - 2,
      y: Math.round(rect.top + rect.height / 2),
    }))
    .find((candidate) => inZone(candidate.x));
  if (!point)
    throw new Error(
      `No line of "${quote}" reaches the ${edge} tap zone, so this tap would prove nothing.`
    );

  tapPoint(doc, view, point.x, point.y);
};

/* ------------------------------------------------------------------ *
 * M3.2 — where the highlight layer collides with the reader around it
 * ------------------------------------------------------------------ */

/** Both highlights of chapter one, drawn, with the first one's dialog open. */
const aBookOfTwoOpenAtTheFirst = async (...extra: Parameters<typeof worker.use>) => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, '#F59E0B'), aMarkedHighlight(302, SECOND_QUOTE, '#3B82F6')],
    [aPlacedLocator(301, FIRST_QUOTE), aPlacedLocator(302, SECOND_QUOTE)],
    {},
    ...extra
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await tintsOnThePage().toEqual([BLUE_TINT, YELLOW_TINT].sort());
  await tapQuoteInPublication(FIRST_QUOTE);
  await expect.element(screen.getByRole('dialog').getByText(FIRST_QUOTE)).toBeVisible();
  return screen;
};

/**
 * Two window-level arrow-key handlers, one book underneath one dialog.
 *
 * The dialog pages between highlights and the reader turns pages, and both
 * listen on the window — so the dialog calling `preventDefault` never reached
 * the reader, and an arrow pressed to see the next highlight also turned the
 * book behind it. Silently: the dialog covers the page, so the reader only
 * found out on closing it, with the new position already written to the server.
 */
test('arrow keys page between highlights without turning the book underneath', async () => {
  const positions = readingPositionApi();
  const screen = await aBookOfTwoOpenAtTheFirst(...positions.handlers);

  await userEvent.keyboard('{ArrowRight}');

  await expect.element(screen.getByRole('dialog').getByText(SECOND_QUOTE)).toBeVisible();
  await expectNoPageTurn();
  expect(positions.writes).toEqual([]);
});

/** And the book is the book's again once the dialog is out of the way. */
test('arrow keys turn the page again once the dialog is closed', async () => {
  const screen = await aBookOfTwoOpenAtTheFirst();

  window.history.back();
  await expect.poll(() => window.location.search).not.toContain('highlightId');
  await userEvent.keyboard('{ArrowRight}');

  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});

/**
 * A phone, a highlight near the edge, and two listeners on one `pointerup`.
 *
 * The tap zones live on the frame's window and Readium reports a decoration
 * activation over `postMessage`, so the page had already turned by the time
 * anything knew the tap belonged to a highlight: the reader got the dialog they
 * asked for and lost their page for it. The zones ask the decoration layer
 * directly now, while the gesture is still in hand.
 */
test('tapping a highlight in a tap zone opens it without turning the page', async () => {
  const positions = readingPositionApi();
  aBookWithHighlights(
    [aMarkedHighlight(301, DENSE_CHAPTER_TEXT, '#F59E0B')],
    [aPlacedLocator(301, DENSE_CHAPTER_TEXT)],
    { denseFirstChapter: true },
    ...positions.handlers
  );
  await page.viewport(PHONE_VIEWPORT.width, PHONE_VIEWPORT.height);

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  await tintsOnThePage().toEqual([YELLOW_TINT]);

  // The forward edge, deliberately: the backward one has nowhere to go from
  // page one, so a page turn there would be invisible and the test vacuous.
  await tapHighlightInTapZone(DENSE_CHAPTER_TEXT, 'right');

  await expect.element(screen.getByRole('dialog')).toBeVisible();
  expect(window.location.search).toContain('highlightId=301');
  await expectNoPageTurn();
  expect(positions.writes).toEqual([]);
});

/** The zones still turn pages where no highlight has claimed the tap. */
test('a tap zone still turns the page beside a highlight', async () => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, '#F59E0B')],
    [aPlacedLocator(301, FIRST_QUOTE)]
  );
  await page.viewport(PHONE_VIEWPORT.width, PHONE_VIEWPORT.height);

  const screen = await renderApp({ path: '/book/1/read' });
  await tintsOnThePage().toEqual([YELLOW_TINT]);

  await gestureInPublication({ across: 0.9 });

  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});

/**
 * A deleted highlight leaves a mark that opens nothing.
 *
 * The book and the locators are two reads that settle separately, so between
 * them the book has lost a highlight the locator list still places — drawn in
 * the default grey, because the label went with the highlight, and inert when
 * tapped, because the dialog has no highlight to show. Pruning the locator
 * cache on the delete closes the window; refusing to draw a locator the loaded
 * book does not claim closes it for every other order these two can settle in.
 *
 * It also asserts what did *not* happen: nothing asked the server to place the
 * book again. That request is the most expensive read in the app (ADR-0004
 * *Amendment 5*) and could only have returned what was already known.
 */
test('deleting a highlight takes its decoration with it and re-derives nothing', async () => {
  let derivations = 0;
  const bookState = aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, '#F59E0B'), aMarkedHighlight(302, SECOND_QUOTE, '#3B82F6')],
    [],
    {},
    http.get('/api/v1/books/:bookId/highlight-locators', () => {
      derivations += 1;
      return HttpResponse.json({
        items: [aPlacedLocator(301, FIRST_QUOTE), aPlacedLocator(302, SECOND_QUOTE)],
      });
    }),
    http.delete('/api/v1/books/:bookId/highlight', async ({ request }) => {
      const body = (await request.json()) as { highlight_ids: number[] };
      const gone = new Set(body.highlight_ids);
      bookState.book = {
        ...bookState.book,
        chapters: bookState.book.chapters.map((chapter) => ({
          ...chapter,
          highlights: chapter.highlights.filter((highlight) => !gone.has(highlight.id)),
        })),
      };
      return HttpResponse.json({ success: true, message: 'Deleted', deleted_count: gone.size });
    })
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await tintsOnThePage().toEqual([BLUE_TINT, YELLOW_TINT].sort());
  await tapQuoteInPublication(FIRST_QUOTE);
  await expect.element(screen.getByRole('dialog').getByText(FIRST_QUOTE)).toBeVisible();

  await userEvent.click(screen.getByRole('button', { name: 'Delete highlight' }));
  await userEvent.click(screen.getByRole('button', { name: 'Delete', exact: true }));

  // The yellow mark is off the page and the blue one is untouched.
  await tintsOnThePage().toEqual([BLUE_TINT]);
  expect(derivations).toBe(1);
});

/**
 * `ui_color` is stored text, and both spellings of a hex colour are in the
 * wild. `alpha()` throws on the bare one, and a throw here happens while a book
 * is being rendered — so the reader shows no book at all, over a label.
 */
test('a label colour stored without its hash is still drawn in that colour', async () => {
  aBookWithHighlights(
    [aMarkedHighlight(301, FIRST_QUOTE, 'F59E0B')],
    [aPlacedLocator(301, FIRST_QUOTE)]
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();

  await tintsOnThePage().toEqual([YELLOW_TINT]);
});

/* ------------------------------------------------------------------ *
 * M3.3 — opening the reader at a highlight (#747)
 * M3.4 — and what happens when it cannot be found (#748)
 * ------------------------------------------------------------------ */

/** The second chapter of the fixture, which is not where the book opens on its own. */
const CHAPTER_TWO = 'resources/OEBPS/chapter2.xhtml';

/** A phrase of the second chapter, so a jump to it is visible in the page readout. */
const SECOND_CHAPTER_QUOTE = 'purest form of generosity';

/** The titles the fixture manifest's contents give the two chapters. */
const CHAPTER_TWO_TITLE = 'On Memory';

/** That highlight's place, in the chapter the book does not open at. */
const aLocatorInChapterTwo = (id: number): HighlightLocatorResponse => ({
  highlight_id: id,
  unavailable: null,
  locator: {
    href: CHAPTER_TWO,
    type: 'application/xhtml+xml',
    locations: {},
    text: { highlight: SECOND_CHAPTER_QUOTE },
  },
});

/**
 * A book whose one highlight is in its second chapter, named by the chapter the
 * manifest's contents also name.
 *
 * The names have to agree, because that is the only thing the fallback below
 * has to go on: a highlight knows its chapter by the name the EPUB's contents
 * gave it at import, and the manifest publishes the same names against hrefs.
 */
const aBookMarkedInItsSecondChapter = (
  highlightLocators: HighlightLocatorResponse[],
  chapterName = CHAPTER_TWO_TITLE,
  ...extra: Parameters<typeof worker.use>
) => {
  worker.use(
    ...bookApi({
      book: aBookDetails({
        title: 'The Pragmatic Reader',
        has_ebook: true,
        chapters: [
          aChapter({
            id: 11,
            name: chapterName,
            chapter_number: 2,
            highlights: [aMarkedHighlight(302, SECOND_CHAPTER_QUOTE, '#3B82F6')],
          }),
        ],
      }),
    }).handlers
  );
  worker.use(...readiumApi({ highlightLocators }));
  if (extra.length) worker.use(...extra);
};

/**
 * The jump the milestone is for: a highlight clicked in a list, and the book
 * opened on the passage it was made on rather than at the beginning.
 *
 * Chapter two, deliberately, because that is not where this book opens on its
 * own — so the page readout is the jump rather than a default. And the dialog is
 * open over it, because `?highlightId=` means "show me this highlight" and
 * showing somebody a highlight is both putting it in front of them and letting
 * them read what they wrote about it.
 */
test('opening the reader at a highlight lands on it, with the highlight open', async () => {
  aBookMarkedInItsSecondChapter([aLocatorInChapterTwo(302)]);

  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });

  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
  await expect.element(screen.getByRole('dialog').getByText(SECOND_CHAPTER_QUOTE)).toBeVisible();
});

/**
 * The other half of that, and the one the interplay turns on: the param opened
 * the dialog *and* moved the book, so dropping it must undo only the dialog.
 *
 * A reader who closes the dialog is looking at the passage they came for. The
 * book going back to where they had left off would take it away from them.
 */
test('closing the highlight leaves the reader on the passage', async () => {
  aBookMarkedInItsSecondChapter([aLocatorInChapterTwo(302)]);

  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });
  await expect.element(screen.getByRole('dialog')).toBeVisible();

  await screen.getByRole('dialog').getByRole('button', { name: 'Close dialog' }).click();

  // The param goes without the history entry it arrived in: a dialog opened
  // *from* the URL has no push of its own to pop, so closing it replaces rather
  // than going back — going back from here is leaving the reader, which is
  // where the reader came from and not what closing a dialog means.
  await expect.poll(() => window.location.search).not.toContain('highlightId');
  await expect.element(screen.getByRole('dialog').query()).toBeNull();
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});

/**
 * Arriving is not reading, and a visit to a highlight must not cost the reader
 * the place they were actually up to.
 *
 * The same bracket M2.4 draws around a restore covers this: everything the
 * navigator says while the book is arriving is the book arriving. The position
 * on the server is still the one the reader left, and stays that way until they
 * turn a page of their own accord.
 */
test('jumping to a highlight does not overwrite where the reader was', async () => {
  const positions = readingPositionApi(aResumePosition());
  aBookMarkedInItsSecondChapter(
    [aLocatorInChapterTwo(302)],
    CHAPTER_TWO_TITLE,
    ...positions.handlers
  );

  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });
  await expect.element(screen.getByRole('dialog')).toBeVisible();

  // Comfortably past the debounce, so a write the arrival provoked would have
  // landed by now.
  await new Promise((resolve) => setTimeout(resolve, 8_000));
  expect(positions.writes).toHaveLength(0);
}, 30_000);

/**
 * A highlight the reader was brought here for has to be findable among the
 * others, and Readium's decoration styles have no "this one" state to borrow —
 * so the tint is what says it, laid on brighter for a moment and fading back to
 * the strength every other mark is drawn at.
 */
test('the highlight a reader arrived at is briefly emphasised', async () => {
  aBookMarkedInItsSecondChapter([aLocatorInChapterTwo(302)]);

  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();

  // Brighter than the 0.35 every other highlight in the book is drawn at.
  await expect
    .poll(() => decorationTints().some((tint) => tint === 'rgba(59, 130, 246, 0.75)'), {
      timeout: DECORATIONS_ARRIVE_WITHIN,
    })
    .toBe(true);

  // And it settles back, so the page is not left with one mark shouting.
  await tintsOnThePage().toEqual([BLUE_TINT]);
});

/** Long enough for the whole emphasis ramp to have run, if one had started. */
const EMPHASIS_RAMP_MS = 1_500;

/**
 * The control for the test above: the same mark, on the same page, reached
 * without asking for it. Emphasis is about *arriving* at a highlight, so a book
 * merely opened where one happens to be must not flash it — otherwise nothing
 * about the brighter tint means anything.
 */
test('a highlight nobody jumped to is drawn at its ordinary strength throughout', async () => {
  aBookMarkedInItsSecondChapter(
    [aLocatorInChapterTwo(302)],
    CHAPTER_TWO_TITLE,
    ...readingPositionApi(aResumePosition()).handlers
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();

  await tintsOnThePage().toEqual([BLUE_TINT]);
  await new Promise((resolve) => setTimeout(resolve, EMPHASIS_RAMP_MS));
  expect([...new Set(decorationTints())]).toEqual([BLUE_TINT]);
});

/**
 * The M3.4 fallback: the server will not place this highlight, and the reader
 * still has somewhere better to be than page one.
 *
 * The chapter is derived on this side, from the two things that name it: the
 * chapter the highlight was made in, and the manifest's own contents. Landing
 * there puts the reader within a page or two of the passage instead of at the
 * front of a book they were part-way through — and they are told, because a
 * book that quietly opens somewhere else looks like one that ignored the link.
 */
test('a highlight that cannot be placed opens its chapter, and says so', async () => {
  aBookMarkedInItsSecondChapter([{ highlight_id: 302, locator: null, unavailable: 'unresolved' }]);

  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });

  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
  await expect
    .element(screen.getByText("Couldn't find this highlight's exact place", { exact: false }))
    .toBeVisible();
});

/**
 * And when even the chapter cannot be found — a highlight made in a chapter this
 * edition's contents do not name — the book opens at its start rather than
 * guessing. The apology changes with it: promising a chapter the reader was not
 * taken to would be worse than the plain sentence.
 */
test('a highlight whose chapter is not in this edition opens at the start', async () => {
  aBookMarkedInItsSecondChapter(
    [{ highlight_id: 302, locator: null, unavailable: 'unresolved' }],
    'A chapter this edition does not have'
  );

  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });

  await expect.element(screen.getByText('Page 1 of 2', { exact: false })).toBeVisible();
  await expect
    .element(screen.getByText("Couldn't find this highlight's place", { exact: false }))
    .toBeVisible();
});

/**
 * A jump beats a resume. Somebody who clicked on a passage is asking to be taken
 * to it, which is an instruction rather than a memory — and the place they left
 * off at is still on the server, waiting for the next ordinary open.
 */
test('a jump wins over the place the reader left off at', async () => {
  const positions = readingPositionApi(
    aResumePosition({
      locator: {
        href: 'resources/OEBPS/chapter1.xhtml',
        type: 'application/xhtml+xml',
        locations: { position: 1, progression: 0, totalProgression: 0 },
      },
    })
  );
  aBookMarkedInItsSecondChapter(
    [aLocatorInChapterTwo(302)],
    CHAPTER_TWO_TITLE,
    ...positions.handlers
  );

  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });

  // Chapter two, where the highlight is — not chapter one, where they stopped.
  await expect.element(screen.getByText('Page 2 of 2', { exact: false })).toBeVisible();
});
