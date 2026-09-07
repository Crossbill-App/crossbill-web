import { aBookDetails } from '@tests/fixtures/book';
import { aResumePosition } from '@tests/fixtures/publication';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import {
  ESCAPE_HATCH,
  noPublication,
  readingPositionApi,
  readiumApi,
  sessionUnauthorizedOnce,
} from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { delay, http, HttpResponse } from 'msw';
import { expect, test, vi } from 'vitest';
import { userEvent } from 'vitest/browser';

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
