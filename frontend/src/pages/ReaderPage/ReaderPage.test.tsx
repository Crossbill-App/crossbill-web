import type {
  PositionList,
  ResumePositionResponse,
  WebPublicationManifest,
} from '@/api/generated/model';
import { ReadiumReader } from '@/components/reader/engine/readium/ReadiumReader.ts';
import { READER_PREFERENCES_KEY } from '@/components/reader/preferences/readerPreferenceStorage.ts';
import { theme } from '@/theme/theme.ts';
import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import {
  aDetailedPositionList,
  aHighlightLocator,
  aManifest,
  anUnplacedHighlight,
  aPassage,
  aResumePosition,
  nowhereToResume,
  PASSAGE_SELECTOR,
} from '@tests/fixtures/publication';
import { expectAWriteOnceTheDebounceRunsOut, fakeTheClock } from '@tests/harness/fakeClock';
import { drawnOn, drawnRanges } from '@tests/harness/paintedHighlights';
import { renderApp } from '@tests/harness/renderApp';
import {
  endOf,
  paragraphsOnThePage,
  rangeOver,
  selectInBook,
  tapAt,
  visibleFrame,
} from '@tests/harness/textSelection';
import { bookApi } from '@tests/msw/bookApi';
import type { HighlightCreationAnswer } from '@tests/msw/readiumApi';
import {
  aHeldFirstChapter,
  aHeldSession,
  aHold,
  highlightCreationApi,
  highlightLocatorApi,
  highlightLocatorsApi,
  noPublication,
  readingPositionApi,
  readiumApi,
} from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { afterEach, expect, onTestFinished, test, vi } from 'vitest';
import { cleanup } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

const MANIFEST_PATH = '/api/v1/readium/books/:bookId/manifest.json';
const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const POSITION_PATH = '/api/v1/readium/books/:bookId/reading-position';

const elementUnderTheAppBar = () => {
  const { left, top, width, height } = document.querySelector('header')!.getBoundingClientRect();
  return document.elementFromPoint(left + width / 2, top + height / 2);
};

type Screen = Awaited<ReturnType<typeof renderApp>>;

const expectTheReaderOpen = async (screen: Screen) => {
  await expect.element(screen.getByRole('button', { name: 'Close reader' })).toBeVisible();
  expect(screen.router.state.location.pathname).toBe('/book/1/read');
};

const aReadableBook = () =>
  bookApi({
    book: aBookDetails({ title: 'The Pragmatic Reader', author: 'Ada Lovelace' }),
  }).handlers;

/** The book open at its first page, which is where every reading test starts. */
const openTheBook = async () => {
  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('0%', { exact: true })).toBeVisible();
  // The label is up while the book is still arriving, when a key is dropped.
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
  return screen;
};

/** How far into the book the footer says the reader is: 0% on page 1 of 2, 50% on page 2. */
const expectProgress = (screen: Screen, percent: string) =>
  expect.element(screen.getByText(percent, { exact: true }), { timeout: 5_000 }).toBeVisible();

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Every turn, jump and open the app asks of the engine from here on.
 *
 * Readium moves the page a round trip into the chapter's frame after it is asked,
 * so a test proves the book stayed put by it never having been asked.
 */
const watchTheEngine = () => {
  const spies = {
    next: vi.spyOn(ReadiumReader.prototype, 'next'),
    previous: vi.spyOn(ReadiumReader.prototype, 'previous'),
    goTo: vi.spyOn(ReadiumReader.prototype, 'goTo'),
    open: vi.spyOn(ReadiumReader.prototype, 'open'),
  };
  onTestFinished(() => Object.values(spies).forEach((spy) => spy.mockRestore()));
  return () => Object.entries(spies).flatMap(([method, spy]) => spy.mock.calls.map(() => method));
};

afterEach(async () => {
  // Unmounted here rather than by the global teardown: the reader writes where
  // it left the reader on its way out, and that write has to land on this
  // test's handlers rather than on the next test's.
  cleanup();
  await sleep(100);
});

test('the book navigation offers to read the book', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1' });
  await screen.getByRole('link', { name: 'Read', exact: true }).click();

  await expectTheReaderOpen(screen);
});

test('the reader opens with the book title and a way out', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1/read' });

  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Close reader' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Manage book' })).not.toBeInTheDocument();
  expect(elementUnderTheAppBar()?.closest('header')).toBeNull();
});

test('closing the reader leads to the book page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1/read' });
  await screen.getByRole('button', { name: 'Close reader' }).click();

  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();
});

test('a session that cannot be started reports it and offers the way back', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  worker.use(http.post(SESSION_PATH, () => new HttpResponse(null, { status: 500 })));

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(
      screen.getByText(
        'The reader could not start a session for this book. Please try again later.'
      )
    )
    .toBeVisible();

  await screen.getByRole('button', { name: 'Back to book' }).click();

  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();
});

test('the book opens at its first page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();

  await expect.element(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
});

/** What ReadiumCSS has written into the chapter on screen, of its user settings. */
const userProperty = (name: string) => {
  const frames = [...document.querySelectorAll<HTMLIFrameElement>('iframe')];
  const shown = frames.find((frame) => frame.getBoundingClientRect().width > 0);
  return shown?.contentDocument?.documentElement.style.getPropertyValue(`--USER__${name}`) ?? '';
};

test('a book opens in one column on a wide screen', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  await openTheBook();

  await expect.poll(() => userProperty('colCount')).toBe('1');
});

test('the next button turns the page and the label follows', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectProgress(screen, '50%');

  await screen.getByRole('button', { name: 'Previous page' }).click();
  await expectProgress(screen, '0%');
});

test('the arrow keys turn the page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();
  const asked = watchTheEngine();

  await userEvent.keyboard('{ArrowRight}');
  // Asked for by the time the key is up, which is what lets `watchTheEngine`
  // prove a key turned nothing.
  expect(asked()).toEqual(['next']);
  await expectProgress(screen, '50%');

  await userEvent.keyboard('{ArrowLeft}');
  await expectProgress(screen, '0%');
});

test('an arrow key pressed before the book is on screen does not jam it', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  const chapter = aHeldFirstChapter();
  worker.use(chapter.handler);

  const screen = await renderApp({ path: '/book/1/read' });
  // Asked for once the navigator is up, which is when it starts listening for keys.
  await expect.poll(chapter.isRequested).toBe(true);
  await expect.element(screen.getByLabelText('Loading the book')).toBeVisible();
  await userEvent.keyboard('{ArrowRight}');
  chapter.release();

  await expectProgress(screen, '0%');
  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectProgress(screen, '50%');
});

test('a book with no EPUB explains there is nothing to read', async () => {
  worker.use(...aReadableBook());
  worker.use(...noPublication);

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(
      screen.getByText(
        'This book has no EPUB file, so there is nothing to read here yet. Upload one to read it in the browser.'
      )
    )
    .toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Back to book' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
});

test('a book whose manifest cannot be read says so and offers a retry', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  worker.use(http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 500 })));

  const screen = await renderApp({ path: '/book/1/read' });

  await expect.element(screen.getByRole('alert')).toBeVisible();

  worker.use(...readiumApi());
  await screen.getByRole('button', { name: 'Try again' }).click();

  await expectProgress(screen, '0%');
});

test('a lapsed session holds the book until it has been renewed', async () => {
  fakeTheClock();
  worker.use(...aReadableBook());
  worker.use(...readiumApi({ expiresIn: 1 }));

  const screen = await openTheBook();

  // The date jumps with no timer run, as on a machine that slept through the cookie.
  vi.setSystemTime(Date.now() + 2_000);
  const session = aHeldSession();
  worker.use(session.handler);
  window.dispatchEvent(new Event('focus'));

  await expect.element(screen.getByText('Reconnecting…')).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();

  session.release();
  await expect.element(screen.getByText('Reconnecting…')).not.toBeInTheDocument();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
});

const openTheContents = async (screen: Screen) => {
  await screen.getByRole('button', { name: 'Contents' }).click();
  return screen.getByRole('navigation', { name: 'Table of contents' });
};

const closeTheContents = async (screen: Screen) => {
  await screen.getByRole('button', { name: 'Close contents' }).click();
  await expect
    .element(screen.getByRole('navigation', { name: 'Table of contents' }))
    .not.toBeInTheDocument();
};

/** A book on screen at its first page, with its contents drawer open. */
const aBookWithItsContentsOpen = async (manifest?: WebPublicationManifest) => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi({ manifest }));
  const screen = await openTheBook();
  return { screen, contents: await openTheContents(screen) };
};

test('the contents drawer lists the chapters the manifest publishes', async () => {
  const { screen, contents } = await aBookWithItsContentsOpen();

  await expect.element(screen.getByRole('dialog', { name: 'Contents' })).toBeVisible();
  await expect.element(contents.getByText('On Attention')).toBeVisible();
  await expect.element(contents.getByText('Part two')).toBeVisible();
  await expect.element(contents.getByText('On Memory')).toBeVisible();

  // The tree is kept rather than flattened: a chapter sits in from its part.
  const indentOf = (title: string) =>
    (contents.getByText(title).element() as HTMLElement).getBoundingClientRect().left;
  expect(indentOf('On Memory')).toBeGreaterThan(indentOf('Part two'));
  expect(indentOf('Part two')).toBe(indentOf('On Attention'));
});

test('the contents mark the chapter being read, and follow the reader out of it', async () => {
  const { screen, contents } = await aBookWithItsContentsOpen();

  await expect
    .element(contents.getByRole('button', { name: 'On Attention' }))
    .toHaveAttribute('aria-current', 'location');
  await expect
    .element(contents.getByRole('button', { name: 'On Memory' }))
    .not.toHaveAttribute('aria-current');
  await closeTheContents(screen);

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectProgress(screen, '50%');

  const reopened = await openTheContents(screen);
  await expect
    .element(reopened.getByRole('button', { name: 'On Memory' }))
    .toHaveAttribute('aria-current', 'location');
  await expect
    .element(reopened.getByRole('button', { name: 'On Attention' }))
    .not.toHaveAttribute('aria-current');
});

/** The nearest ancestor that actually scrolls, whatever MUI happens to call it. */
const scrollerAbove = (node: HTMLElement): HTMLElement | null => {
  for (let el = node.parentElement; el; el = el.parentElement) {
    if (el.scrollHeight > el.clientHeight + 1) return el;
  }
  return null;
};

/** A book whose contents are long enough to push the chapter being read off screen. */
const aLongToc = () =>
  aManifest({
    toc: [
      ...Array.from({ length: 40 }, (_, index) => ({
        href: `resources/OEBPS/front-matter-${index}.xhtml`,
        title: `Front matter ${index}`,
      })),
      { href: 'resources/OEBPS/chapter1.xhtml', title: 'On Attention' },
      { href: 'resources/OEBPS/chapter2.xhtml', title: 'On Memory' },
    ],
  });

test('the contents open scrolled to the chapter being read', async () => {
  const { contents } = await aBookWithItsContentsOpen(aLongToc());

  const marked = contents.getByRole('button', { name: 'On Attention' });
  await expect.element(marked).toHaveAttribute('aria-current', 'location');

  const node = marked.element() as HTMLElement;
  await expect.poll(() => scrollerAbove(node)?.scrollTop ?? 0).toBeGreaterThan(0);

  // And it is genuinely on screen, which is the thing the reader gets.
  const box = node.getBoundingClientRect();
  expect(box.top).toBeGreaterThanOrEqual(0);
  expect(box.bottom).toBeLessThanOrEqual(window.innerHeight);
});

test('a heading that links nowhere cannot be picked', async () => {
  const { contents } = await aBookWithItsContentsOpen();

  await expect
    .element(contents.getByRole('button', { name: 'Part two' }))
    .toHaveAttribute('aria-disabled', 'true');
  await expect
    .element(contents.getByRole('button', { name: 'On Memory' }))
    .not.toHaveAttribute('aria-disabled');
});

test('an entry the manifest leaves untitled is still named', async () => {
  const { contents } = await aBookWithItsContentsOpen(
    aManifest({ toc: [{ href: 'resources/OEBPS/chapter1.xhtml', title: '' }] })
  );

  await expect
    .element(contents.getByRole('button', { name: 'Untitled' }))
    .toHaveAttribute('aria-current', 'location');
});

test('a book with no contents says so', async () => {
  const { contents } = await aBookWithItsContentsOpen(aManifest({ toc: [] }));

  await expect.element(contents.getByRole('status')).toBeVisible();
  expect(contents.getByRole('list').elements()).toHaveLength(0);
});

test('an arrow key with the contents open does not turn the page behind them', async () => {
  await aBookWithItsContentsOpen();
  const asked = watchTheEngine();

  await userEvent.keyboard('{ArrowRight}');

  expect(asked()).toEqual([]);
});

const openTheAppearance = async (screen: Screen) => {
  await screen.getByRole('button', { name: 'Appearance' }).click();
  await expect.element(screen.getByRole('heading', { name: 'Page colour' })).toBeVisible();
  return screen.getByRole('dialog', { name: 'Appearance' });
};

const closeTheAppearance = async (screen: Screen) => {
  await userEvent.keyboard('{Escape}');
  await expect.element(screen.getByRole('dialog', { name: 'Appearance' })).not.toBeInTheDocument();
};

/** A book on screen at its first page, with the appearance popover open over it. */
const aBookWithItsAppearanceOpen = async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  const screen = await openTheBook();
  await openTheAppearance(screen);
  return screen;
};

/** One spacing option, scoped past the alignment section's own "Default". */
const spacingOption = (screen: Screen, name: string) =>
  screen.getByRole('group', { name: 'Spacing' }).getByRole('button', { name });

/** The reader's own frame: the fixed overlay its chrome and the book sit in. */
const readerFrame = (screen: Screen) => {
  const button = screen.getByRole('button', { name: 'Close reader' }).element();
  for (let node = button.parentElement; node; node = node.parentElement) {
    if (getComputedStyle(node).position === 'fixed') return node;
  }
  throw new Error('The reader is not on screen.');
};

const asRgb = (hex: string, opacity?: number) => {
  const channels = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16)).join(', ');
  return opacity === undefined ? `rgb(${channels})` : `rgba(${channels}, ${opacity})`;
};

test('the dark page is painted into the book and into the chrome around it', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  const screen = await openTheBook();
  // Both read before the popover covers them: a role query skips the modal's
  // aria-hidden siblings.
  const frame = readerFrame(screen);
  const label = screen.getByText('0%', { exact: true }).element();
  const { dark } = theme.customColors.readerPage;
  await openTheAppearance(screen);

  await screen.getByRole('button', { name: 'Dark' }).click();

  await expect.poll(() => userProperty('backgroundColor')).toBe(dark.background);
  await expect.poll(() => userProperty('textColor')).toBe(dark.text);
  await expect.poll(() => getComputedStyle(frame).backgroundColor).toBe(asRgb(dark.background));
  // The position label is drawn from the page rather than the theme: the
  // theme's own secondary text is 3.7:1 here, under the 4.5:1 body-text floor.
  expect(getComputedStyle(label).color).toBe(asRgb(dark.text, 0.7));
});

test('a justified alignment reaches the words on the page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  const screen = await openTheBook();
  // The default says nothing at all, which is what leaves the book in charge.
  expect(userProperty('textAlign')).toBe('');
  await openTheAppearance(screen);

  await screen.getByRole('button', { name: 'Justified' }).click();

  await expect.poll(() => userProperty('textAlign')).toBe('justify');
});

test('a looser spacing reaches the words on the page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  const screen = await openTheBook();
  // The default says nothing at all, which is what leaves the book's own spacing.
  expect(userProperty('lineHeight')).toBe('');
  expect(userProperty('paraSpacing')).toBe('');
  expect(userProperty('paraIndent')).toBe('');
  await openTheAppearance(screen);

  await spacingOption(screen, 'Loose').click();

  await expect.poll(() => userProperty('lineHeight')).toBe('1.8');
  await expect.poll(() => userProperty('paraSpacing')).toBe('1rem');
  await expect.poll(() => userProperty('paraIndent')).toBe('1rem');
});

test('a spacing set back to default gives the book its own again', async () => {
  const screen = await aBookWithItsAppearanceOpen();
  await spacingOption(screen, 'Loose').click();
  await expect.poll(() => userProperty('lineHeight')).toBe('1.8');

  await spacingOption(screen, 'Default').click();

  await expect.poll(() => userProperty('lineHeight')).toBe('');
  await expect.poll(() => userProperty('paraSpacing')).toBe('');
  await expect.poll(() => userProperty('paraIndent')).toBe('');
});

test('the automatic column count gives a wide page two columns', async () => {
  const screen = await aBookWithItsAppearanceOpen();

  await screen.getByRole('button', { name: 'Auto' }).click();

  await expect.poll(() => userProperty('colCount')).toBe('2');
});

test('an arrow key with the appearance open does not turn the page behind it', async () => {
  await aBookWithItsAppearanceOpen();
  const asked = watchTheEngine();

  await userEvent.keyboard('{ArrowRight}');

  expect(asked()).toEqual([]);
});

test('a larger font size reaches the words on the page', async () => {
  const screen = await aBookWithItsAppearanceOpen();

  await screen.getByRole('button', { name: 'Larger text' }).click();

  await expect.poll(() => userProperty('fontSize')).toBe('125%');
});

test('an arrow key typed into the font size does not turn the page', async () => {
  const screen = await aBookWithItsAppearanceOpen();

  await screen.getByRole('textbox', { name: 'Font size in percent' }).click();
  const asked = watchTheEngine();

  await userEvent.keyboard('{ArrowRight}');

  expect(asked()).toEqual([]);
});

test('pressing the setting already chosen leaves it chosen', async () => {
  const screen = await aBookWithItsAppearanceOpen();
  const justified = screen.getByRole('button', { name: 'Justified' });
  await justified.click();
  await expect.poll(() => userProperty('textAlign')).toBe('justify');

  await justified.click();

  await expect.element(justified).toHaveAttribute('aria-pressed', 'true');
  expect(userProperty('textAlign')).toBe('justify');
});

/** The book on screen, justified by the reader, with the popover dismissed again. */
const aJustifiedBook = async () => {
  const screen = await aBookWithItsAppearanceOpen();
  await screen.getByRole('button', { name: 'Justified' }).click();
  await expect.poll(() => userProperty('textAlign')).toBe('justify');
  await closeTheAppearance(screen);
  return screen;
};

test('the appearance opens on what the reader has already chosen', async () => {
  const screen = await aJustifiedBook();

  const reopened = await openTheAppearance(screen);

  await expect
    .element(reopened.getByRole('button', { name: 'Justified' }))
    .toHaveAttribute('aria-pressed', 'true');
});

test('an appearance the reader set is still set when the book is opened again', async () => {
  const screen = await aJustifiedBook();
  await screen.getByRole('button', { name: 'Close reader' }).click();
  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();

  await screen.getByRole('link', { name: 'Read', exact: true }).click();

  await expectTheReaderOpen(screen);
  await expect.poll(() => userProperty('textAlign'), { timeout: 5_000 }).toBe('justify');
});

/** The book on screen, opened after this record was left in the browser's storage. */
const aBookOpenedAfterStoring = async (record: string) => {
  window.localStorage.setItem(READER_PREFERENCES_KEY, record);
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  await openTheBook();
};

test('an appearance stored as nonsense opens the book on the defaults', async () => {
  await aBookOpenedAfterStoring('{not json at all');

  await expect.poll(() => userProperty('backgroundColor')).toBe(theme.palette.background.default);
  expect(userProperty('textAlign')).toBe('');
  expect(userProperty('colCount')).toBe('1');
});

test('an appearance of values we do not offer opens the book on the defaults', async () => {
  await aBookOpenedAfterStoring(
    JSON.stringify({
      version: 1,
      pageColor: 'chartreuse',
      fontSize: 1,
      spacing: 'enormous',
      alignment: 'sideways',
      columns: 'three',
    })
  );

  await expect.poll(() => userProperty('backgroundColor')).toBe(theme.palette.background.default);
  expect(userProperty('colCount')).toBe('1');
});

/**
 * The reader's place is written back so that both readers agree where it is,
 * and so that reading in the browser reaches the reading statistics.
 */
const aBookRecordingPositions = async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  const positions = readingPositionApi();
  worker.use(...positions.handlers);
  const requests: Request[] = [];
  // Answering nothing passes the write on to the handler that stores it.
  worker.use(
    http.put(POSITION_PATH, ({ request }) => {
      requests.push(request);
    })
  );
  const screen = await openTheBook();
  return { screen, writes: positions.writes, requests };
};

/** A page read and the reader closed again, well inside the write debounce. */
const readAPageAndLeave = async (screen: Screen) => {
  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectProgress(screen, '50%');

  await screen.getByRole('button', { name: 'Close reader' }).click();
  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();
};

test('turning a page in the reader records where the reader got to', async () => {
  fakeTheClock();
  const { screen, writes } = await aBookRecordingPositions();
  // Nothing yet: where the book opened is where the reader already was.
  expect(writes).toHaveLength(0);

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectProgress(screen, '50%');

  await expectAWriteOnceTheDebounceRunsOut(writes);
  expect(writes[0].locator.href).toBe('resources/OEBPS/chapter2.xhtml');
  expect(writes[0].closing).toBe(false);
});

test('closing the reader writes the last position and closes the session', async () => {
  const { screen, writes } = await aBookRecordingPositions();

  await readAPageAndLeave(screen);

  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0].locator.href).toBe('resources/OEBPS/chapter2.xhtml');
  expect(writes[0].closing).toBe(true);
});

test('the departing write carries the access token', async () => {
  const { screen, requests } = await aBookRecordingPositions();

  await readAPageAndLeave(screen);

  // A Bearer-only route, and a `fetch` sends no interceptor's header for us:
  // without this the reading session is never closed.
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].headers.get('Authorization')).toBe('Bearer test-access-token');
});

/**
 * A book reopened in the browser starts where the reader left off, whichever
 * device they were last reading on, and says so once when it cannot.
 */
const LOST_THE_BOOKMARK = "Couldn't restore your last position, so the book opened at the start.";

const aBookResumingAt = async (stored: ResumePositionResponse, positions?: PositionList) => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi(positions ? { positions } : {}));
  const resume = readingPositionApi(stored);
  worker.use(...resume.handlers);
  const screen = await renderApp({ path: '/book/1/read' });
  return { screen, writes: resume.writes };
};

/**
 * The reader half-way through the second chapter, on a list that numbers that
 * chapter in three: 50% rather than the 25% its head is at. Against
 * `aPositionList` the head of the chapter and the middle of it are both 50%, so
 * a landing that lost its progression would read the same as one that kept it.
 */
const expectHalfwayThroughChapterTwo = (screen: Screen) =>
  expect.element(screen.getByText('50%', { exact: true }), { timeout: 10_000 }).toBeVisible();

/** The reader somewhere in the second chapter, which is never where a book opens. */
const expectChapterTwo = (screen: Screen) =>
  expect.element(screen.getByText('50%', { exact: true }), { timeout: 10_000 }).toBeVisible();

const expectTheApology = (screen: Screen) =>
  expect.element(screen.getByRole('alert').filter({ hasText: LOST_THE_BOOKMARK })).toBeVisible();

test('a book opens where the reader left off', async () => {
  const { screen } = await aBookResumingAt(aResumePosition(), aDetailedPositionList());

  await expectHalfwayThroughChapterTwo(screen);
});

test('a place the e-reader recorded opens the same way', async () => {
  // A place derived from an xpointer carries no position number: the server
  // computes a progression against the EPUB and leaves the position list to
  // whoever holds one.
  const { screen } = await aBookResumingAt(
    aResumePosition({
      source: 'koreader',
      locator: {
        href: 'resources/OEBPS/chapter2.xhtml',
        type: 'application/xhtml+xml',
        locations: { progression: 0.5 },
      },
    }),
    aDetailedPositionList()
  );

  await expectHalfwayThroughChapterTwo(screen);
});

test('restoring a position writes nothing back, and reading on from it is written', async () => {
  fakeTheClock();
  const { screen, writes } = await aBookResumingAt(aResumePosition());
  await expectChapterTwo(screen);

  // Where the book opened is where the reader already was, and writing it back
  // would credit them with a sitting for the act of opening a book. Such a write
  // would fire here and be the one the turn below is counted against.
  await vi.advanceTimersByTimeAsync(10_000);

  await screen.getByRole('button', { name: 'Next page' }).click();

  await expectAWriteOnceTheDebounceRunsOut(writes);
  // Past where they were put back, rather than merely in the same chapter: the
  // resume already had them here, so only the progression is news.
  expect(writes[0].locator.locations?.progression).toBeGreaterThan(0.5);
  expect(writes[0].closing).toBe(false);
});

test('a place that could not be found says so, and the book still opens', async () => {
  const { screen } = await aBookResumingAt({ ...nowhereToResume(), unresolved: true });

  await expectProgress(screen, '0%');
  await expectTheApology(screen);
});

test('a place in a chapter the book no longer has costs a bookmark, not the book', async () => {
  const { screen } = await aBookResumingAt(
    aResumePosition({
      locator: {
        href: 'resources/OEBPS/chapter9.xhtml',
        type: 'application/xhtml+xml',
        locations: { position: 9, progression: 0.5 },
      },
    })
  );

  await expectProgress(screen, '0%');
  await expectTheApology(screen);
});

test('a book reopened in the same tab honours where another device left off', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi({ positions: aDetailedPositionList() }));
  let stored: ResumePositionResponse = nowhereToResume();
  worker.use(http.get(POSITION_PATH, () => HttpResponse.json(stored)));

  const screen = await renderApp({ path: '/book/1/read' });
  await expectProgress(screen, '0%');
  await screen.getByRole('button', { name: 'Close reader' }).click();
  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();

  // The reader carries on elsewhere while the book is shut here.
  stored = aResumePosition();
  await screen.getByRole('link', { name: 'Read', exact: true }).click();

  // The answer this tab already has is the stale one, and it comes back as
  // settled data rather than as pending, so a cache that outlived the first
  // open would be latched before the refetch could land.
  await expectHalfwayThroughChapterTwo(screen);
});

test('a book that would not load keeps the reader their place for the retry', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi({ positions: aDetailedPositionList() }));
  worker.use(...readingPositionApi(aResumePosition()).handlers);
  worker.use(
    http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 503 }), { once: true })
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByRole('alert')).toBeVisible();

  await screen.getByRole('button', { name: 'Try again' }).click();

  // The publication is fetched before a landing is looked at, so a manifest
  // that blipped says nothing about the place — dropping it here would cost a
  // bookmark for the network's mistake, and apologise for it too.
  await expectHalfwayThroughChapterTwo(screen);
});

test('a book nobody has read opens at the start and says nothing', async () => {
  const { screen } = await aBookResumingAt(nowhereToResume());

  await expectProgress(screen, '0%');
  await expect.element(screen.getByRole('alert')).not.toBeInTheDocument();
});

test('coming back to the tab leaves the reader where they were reading', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  let stored: ResumePositionResponse = nowhereToResume();
  worker.use(http.get(POSITION_PATH, () => HttpResponse.json(stored)));
  const screen = await openTheBook();
  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectProgress(screen, '50%');
  // Somewhere else by now, so a second answer would have somewhere to move the book.
  stored = aResumePosition();
  const asked = watchTheEngine();

  window.dispatchEvent(new Event('focus'));
  // Bubbling, as the browser's own does: TanStack Query hears it on the window.
  document.dispatchEvent(new Event('visibilitychange', { bubbles: true }));

  // Where a book opens is settled once it opens. A focus refetch starts a tick
  // after the event, and its answer renders a task after it lands.
  await sleep(0);
  await expect.poll(() => screen.queryClient.isFetching()).toBe(0);
  await sleep(0);
  expect(asked()).toEqual([]);
});

const PLACED_TEXT = 'Attention is the rarest and purest form of generosity.';
const UNPLACED_TEXT = 'The map is not the territory.';

const aBookMarkedAtThePassage = () => {
  const highlights = [aHighlight({ id: 302, text: PLACED_TEXT })];
  worker.use(...bookApi({ book: aBookDetails({ chapters: [aChapter({ highlights })] }) }).handlers);
  worker.use(...readiumApi({ positions: aDetailedPositionList() }));
  const resume = readingPositionApi(aResumePosition());
  worker.use(...resume.handlers);
  worker.use(...highlightLocatorsApi([aPassage(302)]));
  worker.use(...highlightLocatorApi([aPassage(302)]));
  return resume.writes;
};

const aJumpToAPassage = async () => {
  const writes = aBookMarkedAtThePassage();
  const screen = await renderApp({ path: '/book/1/read?highlightId=302' });
  return { screen, writes };
};

// The page readout cannot tell: opening at the progression alone lands a page short
// of the passage and reports the same position.
const isThePassageOnThePage = () =>
  [...document.querySelectorAll('iframe')].some((frame) => {
    const paragraph = frame.contentDocument?.querySelector(PASSAGE_SELECTOR);
    if (!paragraph || frame.style.visibility === 'hidden') return false;
    const { left } = paragraph.getBoundingClientRect();
    return left >= 0 && left < frame.getBoundingClientRect().width;
  });

const expectThePassageOnThePage = () =>
  expect.poll(isThePassageOnThePage, { timeout: 10_000 }).toBe(true);

test('a jump lands on the page holding the passage', async () => {
  await aJumpToAPassage();

  await expectThePassageOnThePage();
});

/** A jump to highlight 302, which the server cannot place, made in a chapter of this name. */
const aJumpToAnUnplacedHighlightIn = async (chapterName: string) => {
  const highlights = [aHighlight({ id: 302 })];
  worker.use(
    ...bookApi({
      book: aBookDetails({ chapters: [aChapter({ name: chapterName, highlights })] }),
    }).handlers
  );
  worker.use(...readiumApi());
  worker.use(...highlightLocatorApi([anUnplacedHighlight(302)]));
  return await renderApp({ path: '/book/1/read?highlightId=302' });
};

test('a highlight that cannot be placed opens its chapter, and says so', async () => {
  const screen = await aJumpToAnUnplacedHighlightIn('On Memory');

  await expectProgress(screen, '50%');
  await expect
    .element(
      screen.getByRole('alert').filter({
        hasText:
          "Couldn't find this highlight's exact place, so the book opened at the start of its chapter.",
      })
    )
    .toBeVisible();
});

test('a highlight whose chapter is not in this edition opens at the start, and says so', async () => {
  const screen = await aJumpToAnUnplacedHighlightIn('On Forgetting');

  await expectProgress(screen, '0%');
  await expect
    .element(
      screen.getByRole('alert').filter({
        hasText: "Couldn't find this highlight's place, so the book opened at the start.",
      })
    )
    .toBeVisible();
});

test('jumping to a highlight writes no reading position', async () => {
  fakeTheClock();
  const { screen, writes } = await aJumpToAPassage();
  await expectThePassageOnThePage();

  await vi.advanceTimersByTimeAsync(10_000);

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectAWriteOnceTheDebounceRunsOut(writes);
  // The page after the passage ends the chapter; the jump itself is short of it.
  expect(writes[0].locator.locations?.progression).toBe(1);
});

test('a book is opened with its highlights drawn on the page', async () => {
  const highlight = aHighlight({ id: 300, label: { ui_color: '#F59E0B' } });
  worker.use(
    ...bookApi({ book: aBookDetails({ chapters: [aChapter({ highlights: [highlight] })] }) })
      .handlers
  );
  worker.use(...readiumApi());
  worker.use(...highlightLocatorsApi([aHighlightLocator(300)]));

  await openTheBook();

  await expect.poll(() => drawnOn(document), { timeout: 5_000 }).toEqual(['p:rarest and purest']);
});

/** Only 300 is placed, so a tap is unambiguous while the dialog still pages over both. */
const aBookWithAPaintedHighlight = async ({
  onLocatorsRequest,
}: { onLocatorsRequest?: () => void } = {}) => {
  const highlights = [
    aHighlight({ id: 300, text: PLACED_TEXT }),
    aHighlight({ id: 301, text: UNPLACED_TEXT }),
  ];
  worker.use(...bookApi({ book: aBookDetails({ chapters: [aChapter({ highlights })] }) }).handlers);
  worker.use(...readiumApi());
  worker.use(...highlightLocatorsApi([aHighlightLocator(300)], { onRequest: onLocatorsRequest }));
  const screen = await openTheBook();
  await expect.poll(() => drawnRanges(document), { timeout: 5_000 }).toHaveLength(1);
  return screen;
};

const tapTheHighlight = async () => {
  const [range] = drawnRanges(document);
  const frame = [...document.querySelectorAll('iframe')].find((candidate) =>
    candidate.contentDocument?.contains(range.startContainer)
  )!;
  const rect = range.getClientRects()[0];
  await userEvent.click(frame, {
    position: { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 },
  });
};

const expectTheDialogShowing = (screen: Screen, text: string) =>
  expect.element(screen.getByRole('dialog').getByText(text)).toBeVisible();

const historyIndex = (screen: Screen) => screen.router.state.location.state.__TSR_index;

const expectBackAtTheBook = async (screen: Screen, indexBeforeTheTap: number) => {
  await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();
  await expectTheReaderOpen(screen);
  expect(screen.router.state.location.search).not.toHaveProperty('highlightId');
  // Closed and gone from history too: an entry left behind reopens the dialog on the next back.
  expect(historyIndex(screen)).toBe(indexBeforeTheTap);
};

test('tapping a highlight opens it', async () => {
  const screen = await aBookWithAPaintedHighlight();

  await tapTheHighlight();

  await expectTheDialogShowing(screen, PLACED_TEXT);
  expect(screen.router.state.location.search).toEqual({ highlightId: 300 });
});

test('a highlight opened in the reader offers no way into the reader', async () => {
  const screen = await aBookWithAPaintedHighlight();

  await tapTheHighlight();

  const dialog = screen.getByRole('dialog');
  await expect
    .element(dialog.getByRole('button', { name: 'Copy link to highlight' }))
    .toBeVisible();
  expect(dialog.getByRole('link', { name: 'Open in reader' }).query()).toBeNull();
});

test('closing a tapped highlight goes back to the book', async () => {
  const screen = await aBookWithAPaintedHighlight();
  const before = historyIndex(screen);
  await tapTheHighlight();
  await expectTheDialogShowing(screen, PLACED_TEXT);

  await screen.getByRole('button', { name: 'Close dialog' }).click();

  await expectBackAtTheBook(screen, before);
});

test('the back button closes a tapped highlight, not the book', async () => {
  const screen = await aBookWithAPaintedHighlight();
  const before = historyIndex(screen);
  await tapTheHighlight();
  await expectTheDialogShowing(screen, PLACED_TEXT);

  window.history.back();

  await expectBackAtTheBook(screen, before);
});

test('arrow keys page between highlights without turning the book underneath', async () => {
  const screen = await aBookWithAPaintedHighlight();
  await tapTheHighlight();
  await expectTheDialogShowing(screen, PLACED_TEXT);
  const asked = watchTheEngine();

  await userEvent.keyboard('{ArrowRight}');

  await expectTheDialogShowing(screen, UNPLACED_TEXT);
  expect(asked()).toEqual([]);
});

test('an arrow key after paging to the last highlight does not turn the book underneath', async () => {
  const screen = await aBookWithAPaintedHighlight();
  await tapTheHighlight();
  await expectTheDialogShowing(screen, PLACED_TEXT);
  // The last highlight disables Next, and focus falls to the dialog's container,
  // which Readium does not count as interactive, so it would turn the page.
  await screen.getByRole('dialog').getByRole('button', { name: 'Next', exact: true }).click();
  await expectTheDialogShowing(screen, UNPLACED_TEXT);
  const asked = watchTheEngine();

  await userEvent.keyboard('{ArrowRight}');

  expect(asked()).toEqual([]);
});

test('deleting a highlight takes its mark off the page and fetches no locators again', async () => {
  let locatorRequests = 0;
  const screen = await aBookWithAPaintedHighlight({
    onLocatorsRequest: () => (locatorRequests += 1),
  });
  await tapTheHighlight();
  await expectTheDialogShowing(screen, PLACED_TEXT);

  await screen.getByRole('button', { name: 'Delete highlight' }).click();
  await expect.element(screen.getByRole('alertdialog', { name: /delete/i })).toBeVisible();
  await screen.getByRole('button', { name: 'Delete', exact: true }).click();

  await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();
  await expect.poll(() => drawnRanges(document)).toEqual([]);
  expect(locatorRequests).toBe(1);
});

test('arrow keys turn the page again once the dialog is closed', async () => {
  const screen = await aBookWithAPaintedHighlight();
  await tapTheHighlight();
  await expectTheDialogShowing(screen, PLACED_TEXT);
  await screen.getByRole('button', { name: 'Close dialog' }).click();
  await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();

  await userEvent.keyboard('{ArrowRight}');

  await expectProgress(screen, '50%');
});

test('arriving takes the highlight back out of the address', async () => {
  const { screen } = await aJumpToAPassage();
  await expectThePassageOnThePage();

  await expect.poll(() => screen.router.state.location.search).toEqual({});
});

test('a chapter in the address opens the book there, and is taken back out of it', async () => {
  worker.use(
    ...bookApi({ book: aBookDetails({ chapters: [aChapter({ id: 11, name: 'On Memory' })] }) })
      .handlers
  );
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1/read?chapterId=11' });

  await expectChapterTwo(screen);
  await expect.poll(() => screen.router.state.location.search).toEqual({});
});

test('tapping the highlight the reader arrived at opens it, and Back closes it', async () => {
  const { screen } = await aJumpToAPassage();
  await expectThePassageOnThePage();
  await expect.poll(() => drawnRanges(document), { timeout: 5_000 }).toHaveLength(1);
  const before = historyIndex(screen);

  await tapTheHighlight();
  await expectTheDialogShowing(screen, PLACED_TEXT);
  window.history.back();

  await expectBackAtTheBook(screen, before);
  await expectThePassageOnThePage();
});

/** The reader open on a server that stores highlight 400 and places it. */
const aBookThatStoresHighlights = async (answer: HighlightCreationAnswer) => {
  const details = bookApi({ book: aBookDetails({ chapters: [aChapter()] }) });
  worker.use(...details.handlers);
  worker.use(...readiumApi());
  let locatorListRequests = 0;
  worker.use(...highlightLocatorsApi([], { onRequest: () => (locatorListRequests += 1) }));
  worker.use(...highlightLocatorApi([aHighlightLocator(400)]));
  const created: number[] = [];
  const creation = highlightCreationApi([answer], {
    onCreated: (id) => {
      created.push(id);
      const highlights = [aHighlight({ id, text: PLACED_TEXT })];
      details.state.book = aBookDetails({ chapters: [aChapter({ highlights })] });
    },
  });
  worker.use(...creation.handlers);
  const screen = await openTheBook();
  return {
    screen,
    bodies: creation.bodies,
    created,
    locatorListRequests: () => locatorListRequests,
  };
};

const pressHighlight = (screen: Screen) =>
  screen
    .getByRole('toolbar', { name: 'Selected text' })
    .getByRole('button', { name: 'Highlight' })
    .click();

/** Highlight pressed over "rarest and purest" on the page the book opens at. */
const aHighlightPressed = async (answer: HighlightCreationAnswer) => {
  const opened = await aBookThatStoresHighlights(answer);
  selectInBook(document, 'rarest and purest');
  await pressHighlight(opened.screen);
  return opened;
};

test('a highlight is drawn before the server answers, from the words selected', async () => {
  const answer = aHold();
  const { bodies, created } = await aHighlightPressed({ until: answer.released });

  await expect.poll(() => drawnOn(document)).toEqual(['p:rarest and purest']);
  expect(created).toEqual([]);
  await expect.poll(() => bodies).toHaveLength(1);
  expect(bodies[0].locator.text?.highlight).toBe('rarest and purest');
  expect(bodies[0].locator.locations?.cssSelector).toBeTruthy();
  answer.release();
  await expect.poll(() => created).toEqual([400]);
});

test('a saved highlight is drawn once, and tapping it opens it', async () => {
  const { screen, created, locatorListRequests } = await aHighlightPressed({ id: 400 });
  await expect.poll(() => created).toEqual([400]);
  await expect.poll(() => screen.queryClient.isFetching()).toBe(0);

  await expect
    .poll(async () => {
      await tapTheHighlight();
      return screen.getByRole('dialog').query() !== null;
    })
    .toBe(true);
  await expectTheDialogShowing(screen, PLACED_TEXT);
  await expect.poll(() => drawnRanges(document)).toHaveLength(1);
  expect(locatorListRequests()).toBe(1);
});

test('a highlight the server cannot place is taken off the page, and asks for more text', async () => {
  const { screen } = await aHighlightPressed({ status: 422, delayMs: 300 });
  await expect.poll(() => drawnRanges(document)).toHaveLength(1);

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Try selecting a little more text.' }))
    .toBeVisible();
  await expect.poll(() => drawnRanges(document)).toEqual([]);
});

test('a passage extended across a page turn is highlighted from its first words to the tapped ones', async () => {
  const { screen, bodies } = await aBookThatStoresHighlights({ id: 400 });
  // The second chapter is the one long enough to run over several pages.
  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectProgress(screen, '50%');
  const chapter = visibleFrame(document)!.contentDocument!;
  const anchor = paragraphsOnThePage(chapter)[0];
  selectInBook(document, 'rarest and purest', anchor);
  await screen
    .getByRole('toolbar', { name: 'Selected text' })
    .getByRole('button', { name: 'Extend' })
    .click();

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expect.poll(() => paragraphsOnThePage(chapter)[0]).toBeGreaterThan(anchor);
  tapAt(chapter, endOf(rangeOver(chapter, 'generosity', paragraphsOnThePage(chapter)[0])));
  await pressHighlight(screen);

  await expect.poll(() => bodies).toHaveLength(1);
  const quote = bodies[0].locator.text?.highlight ?? '';
  expect(quote.startsWith('rarest and purest')).toBe(true);
  expect(quote.endsWith('generosity')).toBe(true);
});
