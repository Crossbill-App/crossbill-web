import { getGetBookDetailsQueryKey } from '@/api/generated/books/books.ts';
import type {
  ChapterWithHighlights,
  Highlight,
  HighlightLabelInBook,
  HighlightLocatorResponse,
  ReadingPositionUpdate,
} from '@/api/generated/model';
import type {
  EbookDecoration,
  EbookTocEntry,
  OpenedEbook,
} from '@/components/reader/engine/EbookReader.ts';
import { READER_PREFERENCES_KEY } from '@/components/reader/preferences/readerPreferenceStorage.ts';
import {
  ReaderShell,
  type ReaderShellProps,
  type ReaderTestKnobs,
} from '@/components/reader/ReaderShell.tsx';
import { SnackbarProvider } from '@/context/SnackbarContext.tsx';
import { theme } from '@/theme/theme.ts';
import { DEFAULT_LABEL_COLOR } from '@/utils/colorUtils.ts';
import { ThemeProvider } from '@mui/material/styles';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FakeEbookReader, aFakeLocation } from '@tests/fakes/FakeEbookReader';
import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import {
  aHighlightLocator,
  aPassage,
  aResumePosition,
  anUnplacedHighlight,
  nowhereToResume,
} from '@tests/fixtures/publication';
import { expectAWriteOnceTheDebounceRunsOut, fakeTheClock } from '@tests/harness/fakeClock';
import { pendingQueryClients } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import {
  highlightCreationApi,
  highlightLocatorApi,
  highlightLocatorsApi,
  readingPositionApi,
  readiumApi,
} from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { DateTime } from 'luxon';
import { HttpResponse, delay, http } from 'msw';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { cleanup, render } from 'vitest-browser-react';
import { page, userEvent } from 'vitest/browser';

const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const RESOURCE_PATH = '/api/v1/readium/books/:bookId/resources/*';
const POSITION_PATH = '/api/v1/readium/books/:bookId/reading-position';
const MANIFEST_URL = `${window.location.origin}/api/v1/readium/books/1/manifest.json`;

/** Narrower than the `sm` breakpoint the reader lays itself out against. */
const PHONE_VIEWPORT = { width: 390, height: 780 };

/** Narrower than any phone the reader is likely to be held in. */
const NARROW_VIEWPORT = { width: 320, height: 640 };

/** `vitest.config.ts`'s own viewport, restored after a test has narrowed it. */
const DEFAULT_VIEWPORT = { width: 1440, height: 900 };

const readers: FakeEbookReader[] = [];

const createReader = () => {
  const reader = new FakeEbookReader();
  readers.push(reader);
  return reader;
};

beforeEach(() => {
  readers.length = 0;
  // The shell reads the book's details for its title and its highlights, so
  // every test needs a book whether or not it is about one. A test with
  // something to say about the book registers its own handlers over these.
  worker.use(...bookApi().handlers);
});

afterEach(async () => {
  // Unmounted here rather than by the global teardown: the shell writes where
  // the reader was on its way out, and that write has to land on this test's
  // handlers rather than on the next test's.
  cleanup();
  await sleep(100);
  showTheTab();
  await page.viewport(DEFAULT_VIEWPORT.width, DEFAULT_VIEWPORT.height);
});

/** Going to another tab, which nothing in a browser lets a test do for real. */
const setVisibility = (state: DocumentVisibilityState) => {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true });
  document.dispatchEvent(new Event('visibilitychange'));
};

const hideTheTab = () => setVisibility('hidden');
const showTheTab = () => setVisibility('visible');

const aSlowSession = (ms: number) =>
  http.post(SESSION_PATH, async () => {
    await delay(ms);
    return HttpResponse.json({ expires_in: 900 });
  });

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// The shell asks the server where to resume and apologises when it cannot, so
// it needs the two providers the app mounts it under.
const shellUnder = (
  queryClient: QueryClient,
  props: Partial<ReaderShellProps>,
  knobs: ReaderTestKnobs
) => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider theme={theme}>
      <SnackbarProvider>
        <ReaderShell
          bookId={1}
          onClose={() => {}}
          {...props}
          testing={{ createReader, ...knobs }}
        />
      </SnackbarProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

const renderShell = async (props: Partial<ReaderShellProps> = {}, knobs: ReaderTestKnobs = {}) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  pendingQueryClients.push(queryClient);
  const screen = await render(shellUnder(queryClient, props, knobs));
  return Object.assign(screen, {
    queryClient,
    rerenderShell: (next: Partial<ReaderShellProps>) =>
      screen.rerender(shellUnder(queryClient, next, knobs)),
  });
};

type Screen = Awaited<ReturnType<typeof renderShell>>;

/** Two chapters, the second without a media type, as many manifests publish them. */
const A_TOC: EbookTocEntry[] = [
  {
    href: 'resources/OEBPS/chapter1.xhtml',
    type: 'application/xhtml+xml',
    title: 'On Attention',
    children: [],
  },
  { href: 'resources/OEBPS/chapter2.xhtml', type: '', title: 'On Memory', children: [] },
];

const aBookWithContents = (): Partial<OpenedEbook> => ({ toc: A_TOC, tocHref: A_TOC[0].href });

/** The shell with the book on screen at its first page. */
const anOpenBook = async (
  opened: Partial<OpenedEbook> = {},
  props: Partial<ReaderShellProps> = {}
) => {
  const screen = await renderShell(props);
  await expect.poll(() => readers.length).toBe(1);
  readers[0].resolveOpen(opened);
  await expect.element(screen.getByText('0%', { exact: true })).toBeVisible();
  return screen;
};

const expectReconnecting = (screen: Screen) =>
  expect.element(screen.getByText('Reconnecting…')).toBeVisible();

test('the shell waits for the cookie before opening the book', async () => {
  worker.use(...readiumApi());
  worker.use(aSlowSession(500));

  const screen = await renderShell();

  expect(readers).toHaveLength(0);
  await expect.poll(() => readers.length).toBe(1);
  expect(readers[0].openedWith.map((opened) => opened.manifestUrl)).toEqual([MANIFEST_URL]);
  await expect.element(screen.getByLabelText('Loading the book')).toBeVisible();
});

test("the book is opened with the reader's appearance", async () => {
  worker.use(...readiumApi());

  await renderShell();

  await expect.poll(() => readers.length).toBe(1);
  expect(readers[0].openedWith[0].appearance).toEqual({
    fontSize: 1,
    lineHeight: null,
    paragraphSpacing: null,
    paragraphIndent: null,
    textAlign: null,
    columnCount: 1,
    // The light page is the app's own off-white rather than publisher white.
    pageBackgroundColor: theme.palette.background.default,
    pageTextColor: theme.palette.text.primary,
  });
});

test('a page turn asked for by the book is forwarded', async () => {
  worker.use(...readiumApi());

  await anOpenBook();

  readers[0].requestPageTurn('next');
  expect(readers[0].nextCalls).toBe(1);

  readers[0].requestPageTurn('previous');
  expect(readers[0].previousCalls).toBe(1);
});

test('a page turn asked for while the cookie is being renewed is dropped', async () => {
  // A one-second cookie has genuinely lapsed by the time the tab comes back,
  // and the scheduled renewal cannot interfere: its floor is five.
  worker.use(...readiumApi({ expiresIn: 1 }));

  const screen = await anOpenBook();

  await sleep(1_200);
  worker.use(aSlowSession(2_000));
  window.dispatchEvent(new Event('focus'));

  await expectReconnecting(screen);
  readers[0].requestPageTurn('next');
  expect(readers[0].nextCalls).toBe(0);

  await expect
    .element(screen.getByText('Reconnecting…'), { timeout: 5_000 })
    .not.toBeInTheDocument();
  readers[0].requestPageTurn('next');
  expect(readers[0].nextCalls).toBe(1);
});

/** How long the reader gives a book to appear. */
const BOOT_TIMEOUT_MS = 15_000;

test('a book that never appears times out and can be retried', async () => {
  fakeTheClock();
  worker.use(...readiumApi());

  const screen = await renderShell();
  await expect.poll(() => readers.length).toBe(1);
  await vi.advanceTimersByTimeAsync(BOOT_TIMEOUT_MS);

  await expect
    .element(screen.getByText('This book could not be opened in the reader.'))
    .toBeVisible();

  await screen.getByRole('button', { name: 'Try again' }).click();

  await expect.poll(() => readers.length).toBe(2);
  expect(readers[0].destroyed).toBe(true);
  // The abandoned first reader rejects as it is aborted, and that rejection
  // must not be read as the second attempt having failed.
  await expect.element(screen.getByLabelText('Loading the book')).toBeVisible();

  readers[1].resolveOpen({ location: aFakeLocation(2) });
  await expect.element(screen.getByText('50%', { exact: true })).toBeVisible();
});

test('a book whose chapters never arrive times out and can be retried', async () => {
  fakeTheClock();
  worker.use(...readiumApi());
  worker.use(http.get(RESOURCE_PATH, () => delay('infinite')));

  const screen = await renderShell({}, { createReader: undefined });

  // Nothing on screen says when the navigator has armed its watchdog.
  await expect
    .poll(async () => {
      await vi.advanceTimersByTimeAsync(BOOT_TIMEOUT_MS / 3);
      return screen.getByText('This book could not be opened in the reader.').query();
    })
    .not.toBeNull();
  await expect.element(screen.getByRole('button', { name: 'Try again' })).toBeVisible();

  worker.use(...readiumApi());
  await screen.getByRole('button', { name: 'Try again' }).click();

  await expect.element(screen.getByText('0%', { exact: true }), { timeout: 5_000 }).toBeVisible();
});

test('the contents are not offered until the book is on screen', async () => {
  worker.use(...readiumApi());

  const screen = await renderShell();

  await expect.element(screen.getByRole('button', { name: 'Contents' })).toBeDisabled();

  await expect.poll(() => readers.length).toBe(1);
  readers[0].resolveOpen(aBookWithContents());

  await expect.element(screen.getByRole('button', { name: 'Contents' })).toBeEnabled();
});

test('picking a contents entry goes there and closes the drawer', async () => {
  worker.use(...readiumApi());

  const screen = await anOpenBook(aBookWithContents());

  await screen.getByRole('button', { name: 'Contents' }).click();
  // The entry the book opened at, which the seam reports through `tocHref` alone.
  await expect
    .element(screen.getByRole('button', { name: 'On Attention' }))
    .toHaveAttribute('aria-current', 'location');

  await screen.getByRole('button', { name: 'On Memory' }).click();

  expect(readers[0].goToCalls).toEqual([
    { href: 'resources/OEBPS/chapter2.xhtml', type: '', locations: {} },
  ]);
  await expect
    .element(screen.getByRole('navigation', { name: 'Table of contents' }))
    .not.toBeInTheDocument();
});

const openTheAppearance = async (screen: Screen) => {
  await screen.getByRole('button', { name: 'Appearance' }).click();
  await expect.element(screen.getByRole('dialog', { name: 'Appearance' })).toBeVisible();
};

const theFontSize = (screen: Screen) =>
  screen.getByRole('textbox', { name: 'Font size in percent' });

/** The popover open over a book whose engine reports the fake's own font-size range. */
const anOpenAppearance = async () => {
  worker.use(...readiumApi());
  const screen = await anOpenBook();
  await openTheAppearance(screen);
  return screen;
};

const fontSizes = () => readers[0].appearances.map((appearance) => appearance.fontSize);

test('the font size opens on what the book is showing, and steps by a quarter', async () => {
  const screen = await anOpenAppearance();

  await expect.element(theFontSize(screen)).toHaveValue('100');

  await screen.getByRole('button', { name: 'Larger text' }).click();

  await expect.element(theFontSize(screen)).toHaveValue('125');
  expect(fontSizes()).toEqual([1.25]);
});

test("the larger button stops the size at the top of the engine's range", async () => {
  const screen = await anOpenAppearance();
  const larger = screen.getByRole('button', { name: 'Larger text' });
  // Not a whole number of steps below the fake's ceiling of 2, so the press
  // that follows has something to clamp.
  await userEvent.fill(theFontSize(screen), '190');
  await userEvent.keyboard('{Enter}');

  await larger.click();

  await expect.element(theFontSize(screen)).toHaveValue('200');
  await expect.element(larger).toBeDisabled();
  expect(fontSizes()).toEqual([1.9, 2]);
});

test("the smaller button stops the size at the bottom of the engine's range", async () => {
  const screen = await anOpenAppearance();
  const smaller = screen.getByRole('button', { name: 'Smaller text' });

  // A second quarter down from where the book opened is past the fake's floor.
  await smaller.click();
  await smaller.click();

  await expect.element(theFontSize(screen)).toHaveValue('60');
  await expect.element(smaller).toBeDisabled();
  expect(fontSizes()).toEqual([0.75, 0.6]);
});

test('the size the book opened at is still within reach of the buttons', async () => {
  const screen = await anOpenAppearance();
  const smaller = screen.getByRole('button', { name: 'Smaller text' });
  const larger = screen.getByRole('button', { name: 'Larger text' });
  await smaller.click();
  await smaller.click();
  await expect.element(theFontSize(screen)).toHaveValue('60');

  await larger.click();
  await larger.click();

  // The floor does not sit on a quarter, and a reader who pokes at the buttons
  // and changes their mind has to be able to get back to where they started.
  await expect.element(theFontSize(screen)).toHaveValue('100');
  expect(fontSizes()).toEqual([0.75, 0.6, 0.75, 1]);
});

test('a size typed between two steps steps to the nearer one', async () => {
  const screen = await anOpenAppearance();
  await userEvent.fill(theFontSize(screen), '103');
  await userEvent.keyboard('{Enter}');

  await screen.getByRole('button', { name: 'Larger text' }).click();

  await expect.element(theFontSize(screen)).toHaveValue('125');
  expect(fontSizes()).toEqual([1.03, 1.25]);
});

test('the arrow keys step the size the field is showing', async () => {
  const screen = await anOpenAppearance();
  await theFontSize(screen).click();

  await userEvent.keyboard('{ArrowUp}');
  await expect.element(theFontSize(screen)).toHaveValue('125');

  await userEvent.keyboard('{ArrowDown}');
  await expect.element(theFontSize(screen)).toHaveValue('100');
  expect(fontSizes()).toEqual([1.25, 1]);
});

test('a size typed into the field reaches the book', async () => {
  const screen = await anOpenAppearance();

  await userEvent.fill(theFontSize(screen), '140');
  await userEvent.keyboard('{Enter}');

  expect(fontSizes()).toEqual([1.4]);
});

test("a size typed past the engine's range is brought inside it", async () => {
  const screen = await anOpenAppearance();

  await userEvent.fill(theFontSize(screen), '900');
  await userEvent.keyboard('{Enter}');

  await expect.element(theFontSize(screen)).toHaveValue('200');
  expect(fontSizes()).toEqual([2]);
});

test('a field cleared and left alone leaves the size as it was', async () => {
  const screen = await anOpenAppearance();

  await userEvent.fill(theFontSize(screen), '');
  await userEvent.tab();

  await expect.element(theFontSize(screen)).toHaveValue('100');
  expect(fontSizes()).toEqual([]);
});

test('a size being typed reaches the book only once it is committed', async () => {
  const screen = await anOpenAppearance();

  await userEvent.fill(theFontSize(screen), '1');
  await userEvent.fill(theFontSize(screen), '15');
  await userEvent.fill(theFontSize(screen), '150');

  expect(fontSizes()).toEqual([]);

  await userEvent.keyboard('{Enter}');

  expect(fontSizes()).toEqual([1.5]);
});

test('a spacing chosen in the popover reaches the engine', async () => {
  const screen = await anOpenAppearance();

  await screen.getByRole('button', { name: 'Tight' }).click();

  expect(readers[0].appearances).toHaveLength(1);
  expect(readers[0].appearances[0]).toMatchObject({
    lineHeight: 1.2,
    // Tight squeezes the lines and leaves the paragraph breaks as the book set them.
    paragraphSpacing: null,
    paragraphIndent: null,
  });
});

test('a page colour chosen in the popover reaches the engine', async () => {
  worker.use(...readiumApi());

  const screen = await anOpenBook();
  await openTheAppearance(screen);

  await screen.getByRole('button', { name: 'Dark' }).click();

  expect(readers[0].appearances).toHaveLength(1);
  expect(readers[0].appearances[0]).toMatchObject({
    pageBackgroundColor: theme.customColors.readerPage.dark.background,
    pageTextColor: theme.customColors.readerPage.dark.text,
  });
});

/** What the browser is drawing a chrome control in, resolved. */
const drawnIn = (screen: Screen, label: string) =>
  getComputedStyle(screen.getByRole('button', { name: label }).element()).color;

/**
 * A page colour is not only the words: the controls on the page are on the page
 * too.
 *
 * The toolbar's buttons were left on `IconButton`'s default, which is
 * `action.active` — black at 54%, stated for the app's light surfaces and fixed
 * there. On the dark page the title and the page-turn chevrons went light and
 * the three buttons beside them stayed black, which is the bar's whole set of
 * ways out sitting all but invisible on it.
 */
test('the chrome controls are drawn in the page colour, not the app palette', async () => {
  worker.use(...readiumApi());

  const screen = await anOpenBook();
  const onTheLightPage = theme.customColors.readerPage.light.text;
  const onTheDarkPage = theme.customColors.readerPage.dark.text;

  for (const label of ['Contents', 'Appearance', 'Close reader', 'Next page']) {
    expect(drawnIn(screen, label), label).toBe(asRgb(onTheLightPage));
  }

  await openTheAppearance(screen);
  await screen.getByRole('button', { name: 'Dark' }).click();
  // Dismissed before the bar is read: the popover is modal, and it hides the
  // chrome behind it from the accessibility tree along with everything else.
  await userEvent.keyboard('{Escape}');
  await expect.element(screen.getByRole('dialog', { name: 'Appearance' })).not.toBeInTheDocument();

  // Polled on the first of them: the page colour lands with a render, and which
  // one is not this test's business.
  await expect.poll(() => drawnIn(screen, 'Contents')).toBe(asRgb(onTheDarkPage));
  for (const label of ['Appearance', 'Close reader', 'Next page']) {
    expect(drawnIn(screen, label), label).toBe(asRgb(onTheDarkPage));
  }
});

/** A `#rrggbb` from the theme, as `getComputedStyle` gives it back. */
const asRgb = (hex: string) => {
  const [, r, g, b] = /^#(\w\w)(\w\w)(\w\w)$/.exec(hex)!;
  return `rgb(${parseInt(r, 16)}, ${parseInt(g, 16)}, ${parseInt(b, 16)})`;
};

/** A whole appearance, none of it the default, as the storage holds it. */
const A_STORED_APPEARANCE = {
  version: 1,
  pageColor: 'dark',
  fontSize: 1.5,
  spacing: 'tight',
  alignment: 'justified',
  columns: 'auto',
};

const seedPreferences = (record: object) =>
  window.localStorage.setItem(READER_PREFERENCES_KEY, JSON.stringify(record));

const storedPreferences = () =>
  JSON.parse(window.localStorage.getItem(READER_PREFERENCES_KEY) ?? 'null') as {
    pageColor?: string;
    highlightColor?: string;
  } | null;

test('the book is opened with the appearance left in storage', async () => {
  worker.use(...readiumApi());
  seedPreferences(A_STORED_APPEARANCE);

  await renderShell();

  await expect.poll(() => readers.length).toBe(1);
  expect(readers[0].openedWith[0].appearance).toMatchObject({
    fontSize: 1.5,
    lineHeight: 1.2,
    textAlign: 'justify',
    columnCount: null,
    pageBackgroundColor: theme.customColors.readerPage.dark.background,
  });
});

test("a stored font size past the engine's range is pulled back into it", async () => {
  worker.use(...readiumApi());
  seedPreferences({ ...A_STORED_APPEARANCE, fontSize: 12 });

  await renderShell();

  await expect.poll(() => readers.length).toBe(1);
  // The store no longer knows the range, so the book opens on what was written
  // down and the engine's own answer corrects it.
  expect(readers[0].openedWith[0].appearance.fontSize).toBe(12);
  readers[0].resolveOpen();
  await expect.poll(() => readers[0].appearances.map((one) => one.fontSize)).toEqual([2]);
});

test("a stored font size inside the engine's range is left where it is", async () => {
  worker.use(...readiumApi());
  seedPreferences(A_STORED_APPEARANCE);

  await anOpenBook();

  expect(readers[0].openedWith[0].appearance.fontSize).toBe(1.5);
  expect(readers[0].appearances).toEqual([]);
});

test('a setting chosen in the popover is written down', async () => {
  const screen = await anOpenAppearance();

  await screen.getByRole('button', { name: 'Dark' }).click();

  expect(storedPreferences()?.pageColor).toBe('dark');
});

test('an appearance from a newer version is read past and left alone', async () => {
  const fromANewerReader = JSON.stringify({ ...A_STORED_APPEARANCE, version: 2 });
  window.localStorage.setItem(READER_PREFERENCES_KEY, fromANewerReader);
  const screen = await anOpenAppearance();
  expect(readers[0].openedWith[0].appearance.pageBackgroundColor).toBe(
    theme.palette.background.default
  );

  await screen.getByRole('button', { name: 'Justified' }).click();

  expect(readers[0].appearances).toHaveLength(1);
  expect(window.localStorage.getItem(READER_PREFERENCES_KEY)).toBe(fromANewerReader);
});

test('opening the appearance and closing it again leaves the book alone', async () => {
  worker.use(...readiumApi());

  const screen = await anOpenBook();
  await openTheAppearance(screen);

  await userEvent.keyboard('{Escape}');

  await expect.element(screen.getByRole('dialog', { name: 'Appearance' })).not.toBeInTheDocument();
  expect(readers[0].appearances).toEqual([]);
});

test('closing the shell destroys the reader', async () => {
  worker.use(...readiumApi());

  const screen = await anOpenBook();
  screen.unmount();

  await expect.poll(() => readers[0].destroyed).toBe(true);
});

/**
 * Where the reader gets to is written back, so that the two readers agree and
 * so that reading in the browser reaches the reading statistics.
 */

/** How long a reader stays quiet before a beat says they are still there. */
const HEARTBEAT_MS = 10 * 60 * 1000;

/** The shell open over position handlers that remember what the reader wrote. */
const aBookRecordingPositions = async () => {
  worker.use(...readiumApi());
  const positions = readingPositionApi();
  worker.use(...positions.handlers);
  const screen = await anOpenBook();
  return { screen, writes: positions.writes };
};

test('turning a page writes the new position, once the reader settles', async () => {
  fakeTheClock();
  const { writes } = await aBookRecordingPositions();

  readers[0].reportLocation(aFakeLocation(2));

  await expectAWriteOnceTheDebounceRunsOut(writes);
  expect(writes[0].locator.href).toBe('resources/OEBPS/chapter2.xhtml');
  expect(writes[0].locator.locations?.position).toBe(2);
  expect(writes[0].closing).toBe(false);
});

test('a run of page turns is written once, and only once it has stopped', async () => {
  fakeTheClock();
  const { writes } = await aBookRecordingPositions();

  readers[0].reportLocation(aFakeLocation(2));
  await vi.advanceTimersByTimeAsync(4_000);
  readers[0].reportLocation(aFakeLocation(1));
  // Past the first turn's own deadline: a reader still turning pages has not
  // settled anywhere, so the wait starts again rather than running out.
  await vi.advanceTimersByTimeAsync(4_000);
  readers[0].reportLocation(aFakeLocation(3));

  await expectAWriteOnceTheDebounceRunsOut(writes);
  expect(writes[0].locator.locations?.position).toBe(3);
});

test('a beat that writes a move still waiting leaves nothing waiting', async () => {
  fakeTheClock();
  worker.use(...readiumApi());
  const positions = readingPositionApi();
  worker.use(...positions.handlers);
  const { writes } = positions;
  const screen = await renderShell();
  await expect.poll(() => readers.length).toBe(1);
  await vi.advanceTimersByTimeAsync(1_000);
  readers[0].resolveOpen();
  await expect.element(screen.getByText('0%', { exact: true })).toBeVisible();

  // The beat is checked every five minutes from mount, so with the book a second
  // late the first beat comes at the third check, a few seconds after this move.
  await vi.advanceTimersByTimeAsync(HEARTBEAT_MS * 1.5 - 4_000);
  readers[0].reportLocation(aFakeLocation(2));
  // Short of the debounce, so only the beat can have written it.
  await vi.advanceTimersByTimeAsync(3_500);
  await expect.poll(() => writes.length, { timeout: 500 }).toBe(1);
  await vi.advanceTimersByTimeAsync(6_500);

  // A move the beat left waiting would be written again here, before the next one.
  readers[0].reportLocation(aFakeLocation(3));
  await expect
    .poll(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
      return writes.map((write) => write.locator.locations?.position);
    })
    .toEqual([2, 3]);
});

/** A write already waiting would fire in the jump and be the one the next turn is counted as. */
const expectNothingWrittenBeforeTheNextTurn = async (writes: ReadingPositionUpdate[]) => {
  await vi.advanceTimersByTimeAsync(10_000);
  readers[0].reportLocation(aFakeLocation(2));
  await expectAWriteOnceTheDebounceRunsOut(writes);
  expect(writes[0].locator.locations?.position).toBe(2);
};

test('a reader who has not moved writes nothing at all', async () => {
  fakeTheClock();
  const { writes } = await aBookRecordingPositions();

  // A preference change, a resize and a re-render all re-announce the same place.
  readers[0].reportLocation(aFakeLocation(1));

  await expectNothingWrittenBeforeTheNextTurn(writes);
});

test('the position the book opened at is never written', async () => {
  fakeTheClock();
  const { writes } = await aBookRecordingPositions();

  await expectNothingWrittenBeforeTheNextTurn(writes);
});

test('a reader who stays on one page is still recorded', async () => {
  fakeTheClock();
  const { writes } = await aBookRecordingPositions();
  const openedAt = Date.now();

  await expect
    .poll(async () => {
      await vi.advanceTimersByTimeAsync(HEARTBEAT_MS / 2);
      return writes.length;
    })
    .toBeGreaterThan(0);
  expect(writes[0].locator.locations?.position).toBe(1);
  expect(writes[0].closing).toBe(false);
  // The observation's own moment rather than the beat's: the reader is still
  // here, not somewhere new.
  expect(Date.parse(writes[0].recorded_at)).toBeLessThanOrEqual(openedAt);
});

test('a hidden tab writes what is pending and leaves the session open', async () => {
  const { writes } = await aBookRecordingPositions();
  readers[0].reportLocation(aFakeLocation(2));

  hideTheTab();

  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0].locator.locations?.position).toBe(2);
  expect(writes[0].closing).toBe(false);
});

test('closing the reader writes the last position and ends the session', async () => {
  const { screen, writes } = await aBookRecordingPositions();
  readers[0].reportLocation(aFakeLocation(2));

  screen.unmount();

  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0].locator.locations?.position).toBe(2);
  expect(writes[0].closing).toBe(true);
});

test('a book opened and closed again without being read writes nothing', async () => {
  const { screen, writes } = await aBookRecordingPositions();

  screen.unmount();

  await sleep(300);
  expect(writes).toEqual([]);
});

/**
 * A book reopened in the browser starts where the reader left off, on whatever
 * device they were last reading. Where a place cannot be restored the book
 * still opens, and says so once.
 */
const LOST_THE_BOOKMARK = "Couldn't restore your last position, so the book opened at the start.";

const aSlowResumeAnswer = (ms: number) =>
  http.get(POSITION_PATH, async () => {
    await delay(ms);
    return HttpResponse.json(nowhereToResume());
  });

/** The shell over a place stored part-way through the book's second chapter. */
const aResumedBook = async () => {
  worker.use(...readiumApi());
  worker.use(...readingPositionApi(aResumePosition()).handlers);
  const screen = await renderShell();
  await expect.poll(() => readers.length).toBe(1);
  return screen;
};

test('the book is not opened until the resume answer is in', async () => {
  worker.use(...readiumApi());
  worker.use(aSlowResumeAnswer(500));

  const screen = await renderShell();

  // The cookie is minted long before the answer, and a navigator takes its
  // initial position once, at construction.
  await sleep(250);
  expect(readers).toHaveLength(0);
  await expect.element(screen.getByLabelText('Loading the book')).toBeVisible();

  await expect.poll(() => readers.length).toBe(1);
});

test('the book is opened at the place the reader left off', async () => {
  await aResumedBook();

  expect(readers[0].openedWith[0].initialLocation).toEqual({
    href: 'resources/OEBPS/chapter2.xhtml',
    type: 'application/xhtml+xml',
    locations: { position: 2, progression: 0.5, totalProgression: 0.75 },
  });
});

/** The navigator refusing the place it was offered, and the retry opening without one. */
const refuseTheLanding = async (retried: Partial<OpenedEbook> = {}) => {
  readers[0].rejectOpen();
  await expect.poll(() => readers.length).toBe(2);
  expect(readers[1].openedWith[0].initialLocation).toBeUndefined();
  readers[1].resolveOpen(retried);
};

test('a landing the navigator refuses is retried once, without it', async () => {
  const screen = await aResumedBook();

  await refuseTheLanding();

  await expect.element(screen.getByText('0%', { exact: true })).toBeVisible();
  // The place is gone either way, so the reader is owed the same sentence as if
  // it had never been found.
  await expect
    .element(screen.getByRole('alert').filter({ hasText: LOST_THE_BOOKMARK }))
    .toBeVisible();
});

test('a second refusal is a real failure, not a third attempt', async () => {
  const screen = await aResumedBook();
  readers[0].rejectOpen();
  await expect.poll(() => readers.length).toBe(2);

  readers[1].rejectOpen();

  await expect
    .element(screen.getByText('The book could not be opened. Please try again later.'))
    .toBeVisible();
  expect(readers).toHaveLength(2);
});

const THE_PASSAGE = aPassage(300).locator;

const BOOK_DETAILS_PATH = '/api/v1/books/:bookId';

/** A chapter of the book holding highlight 300. */
const theChapterOf300 = (overrides: Partial<ChapterWithHighlights> = {}) =>
  aChapter({ highlights: [aHighlight({ id: 300 })], ...overrides });

/** The shell opened at highlight 300, with a place to resume from also on offer. */
const aJump = async (
  locators: HighlightLocatorResponse[] = [aPassage(300)],
  chapters: ChapterWithHighlights[] = [theChapterOf300({ name: 'On Memory' })],
  { detailsDelayMs = 0 } = {}
) => {
  worker.use(...readiumApi());
  worker.use(...readingPositionApi(aResumePosition()).handlers);
  worker.use(...bookApi({ book: aBookDetails({ chapters }) }).handlers);
  if (detailsDelayMs) {
    worker.use(
      http.get(BOOK_DETAILS_PATH, async () => {
        await delay(detailsDelayMs);
      })
    );
  }
  let resumeRequests = 0;
  // Answering nothing passes the request on to the handler that answers it.
  worker.use(
    http.get(POSITION_PATH, () => {
      resumeRequests += 1;
    })
  );
  worker.use(...highlightLocatorApi(locators));
  const screen = await renderShell({ target: { kind: 'highlight', id: 300 } });
  await expect.poll(() => readers.length).toBe(1);
  return { screen, resumeRequests: () => resumeRequests };
};

const expectOnScreen = (screen: Screen) =>
  expect
    .element(screen.getByRole('button', { name: 'Contents' }), { timeout: 5_000 })
    .toBeEnabled();

/** Given the time an apology would take to appear, so its absence means something. */
const expectNoApology = async (screen: Screen) => {
  await sleep(300);
  expect(screen.getByRole('alert').query()).toBeNull();
};

const MISSED_THE_HIGHLIGHT =
  "Couldn't find this highlight's exact place, so the book opened at the start of its chapter.";
const MISSED_THE_CHAPTER_TOO =
  "Couldn't find this highlight's place, so the book opened at the start.";
const CHAPTER_NOT_IN_THE_BOOK =
  "Couldn't find this chapter in the book, so it opened at the start.";

const expectToBeTold = (screen: Screen, message: string) =>
  expect.element(screen.getByRole('alert').filter({ hasText: message })).toBeVisible();

const THE_START_OF_ON_MEMORY = { href: A_TOC[1].href, type: '', locations: {} };

/** The latest reader gone on to the start of On Memory, and the reader told it is the chapter. */
const expectTheChapterFallback = async (screen: Screen) => {
  await expectOnScreen(screen);
  expect(readers[readers.length - 1].goToCalls).toEqual([THE_START_OF_ON_MEMORY]);
  await expectToBeTold(screen, MISSED_THE_HIGHLIGHT);
};

test('a jump opens the book at the highlight, not at the place the reader left off', async () => {
  const { resumeRequests } = await aJump();

  expect(readers[0].openedWith[0].initialLocation).toEqual(THE_PASSAGE);
  expect(resumeRequests()).toBe(0);
});

test('the book is not shown until the move to the highlight has finished', async () => {
  const { screen } = await aJump();
  let arrive!: () => void;
  readers[0].goToOutcome = new Promise((resolve) => (arrive = resolve));

  readers[0].resolveOpen({ landedAt: 'requested' });
  await expect.poll(() => readers[0].goToCalls).toEqual([THE_PASSAGE]);
  readers[0].reportLocation(aFakeLocation(2));
  await sleep(300);
  await expect.element(screen.getByRole('button', { name: 'Contents' })).toBeDisabled();

  arrive();

  await expectOnScreen(screen);
  await expect.element(screen.getByText('50%', { exact: true })).toBeVisible();
});

test('a move to the highlight that never finishes still shows the book', async () => {
  const { screen } = await aJump();
  readers[0].goToOutcome = new Promise(() => {});

  readers[0].resolveOpen({ landedAt: 'requested' });

  await expectOnScreen(screen);
});

test('a jump that lands on its passage says nothing', async () => {
  const { screen } = await aJump();

  readers[0].resolveOpen({ toc: A_TOC, landedAt: 'requested' });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([THE_PASSAGE]);
  await expectNoApology(screen);
});

test('a highlight id that changes while the book is on its way does not move it', async () => {
  worker.use(...readiumApi());
  worker.use(...bookApi().handlers);
  worker.use(...highlightLocatorApi([aPassage(300), aHighlightLocator(301)], { delayMs: 300 }));
  const screen = await renderShell({ target: { kind: 'highlight', id: 300 } });

  await screen.rerenderShell({ target: { kind: 'highlight', id: 301 } });
  await expect.poll(() => readers.length).toBe(1);
  readers[0].resolveOpen({ landedAt: 'requested' });
  await expectOnScreen(screen);

  expect(readers).toHaveLength(1);
  expect(readers[0].openedWith[0].initialLocation).toEqual(THE_PASSAGE);
  expect(readers[0].goToCalls).toEqual([THE_PASSAGE]);
});

test('a jump the navigator refused falls back to the chapter, and says so', async () => {
  const { screen } = await aJump();

  await refuseTheLanding({ toc: A_TOC });

  await expectTheChapterFallback(screen);
});

test.each([
  ['a highlight the server could not place', [anUnplacedHighlight(300)]],
  ['a highlight that no longer exists', []],
])('%s opens its chapter, and says so', async (_, locators) => {
  const { screen } = await aJump(locators);

  expect(readers[0].openedWith[0].initialLocation).toBeUndefined();
  readers[0].resolveOpen({ toc: A_TOC });

  await expectTheChapterFallback(screen);
});

test("a highlight whose chapter this edition's contents do not name opens at the start, and says so", async () => {
  const { screen } = await aJump(
    [anUnplacedHighlight(300)],
    [theChapterOf300({ name: 'On Forgetting' })]
  );

  readers[0].resolveOpen({ toc: A_TOC });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([]);
  await expectToBeTold(screen, MISSED_THE_CHAPTER_TOO);
});

test("a jump waits for the book's chapters before opening", async () => {
  const { screen } = await aJump([anUnplacedHighlight(300)], undefined, { detailsDelayMs: 500 });

  readers[0].resolveOpen({ toc: A_TOC });

  await expectTheChapterFallback(screen);
});

test('a locator that names only a resource is reported as landing on the chapter', async () => {
  const { screen } = await aJump([
    {
      highlight_id: 300,
      locator: { href: A_TOC[1].href, type: 'application/xhtml+xml', locations: {}, text: {} },
    },
  ]);

  readers[0].resolveOpen({ toc: A_TOC, landedAt: 'requested' });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([]);
  await expectToBeTold(screen, MISSED_THE_HIGHLIGHT);
});

test('a locator whose resource this edition lacks falls back to the chapter', async () => {
  const { screen } = await aJump();

  readers[0].resolveOpen({ toc: A_TOC, landedAt: 'start' });

  await expectTheChapterFallback(screen);
});

const anIntroduction = (href: string): EbookTocEntry => ({
  href,
  type: 'application/xhtml+xml',
  title: 'Introduction',
  children: [],
});

/** Two parts, each opening with an introduction, under headings that link nowhere. */
const A_TOC_OF_PARTS: EbookTocEntry[] = [
  { href: '#', type: '', title: 'Part one', children: [anIntroduction('part1/intro.xhtml')] },
  { href: '#', type: '', title: 'Part two', children: [anIntroduction('part2/intro.xhtml')] },
];

/** Where the second part begins, its own heading linking nowhere. */
const THE_START_OF_PART_TWO = {
  href: 'part2/intro.xhtml',
  type: 'application/xhtml+xml',
  locations: {},
};

test('a repeated chapter title falls back to the right one of them', async () => {
  // Numbered against their ids, so an order by id would pick the first part's.
  const { screen } = await aJump(
    [anUnplacedHighlight(300)],
    [
      theChapterOf300({ id: 10, name: 'Introduction', chapter_number: 3 }),
      aChapter({ id: 20, name: 'Introduction', chapter_number: 1 }),
      aChapter({ id: 30, name: 'On Attention', chapter_number: 2 }),
    ]
  );

  readers[0].resolveOpen({ toc: A_TOC_OF_PARTS });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([THE_START_OF_PART_TWO]);
  await expectToBeTold(screen, MISSED_THE_HIGHLIGHT);
});

test('an ambiguous chapter title falls back to the start instead of guessing', async () => {
  const { screen } = await aJump(
    [anUnplacedHighlight(300)],
    [theChapterOf300({ name: 'Introduction' })]
  );

  readers[0].resolveOpen({ toc: A_TOC_OF_PARTS });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([]);
  await expectToBeTold(screen, MISSED_THE_CHAPTER_TOO);
});

test('a chapter title the contents name once is the fallback, however often the book repeats it', async () => {
  const { screen } = await aJump(
    [anUnplacedHighlight(300)],
    [
      aChapter({ id: 10, name: 'On Memory', chapter_number: 1 }),
      theChapterOf300({ id: 20, name: 'On Memory', chapter_number: 2 }),
    ]
  );

  readers[0].resolveOpen({ toc: A_TOC });

  await expectTheChapterFallback(screen);
});

test('a chapter title differing only in spacing and case still matches', async () => {
  const { screen } = await aJump(
    [anUnplacedHighlight(300)],
    [theChapterOf300({ name: '  on MEMORY\n' })]
  );

  readers[0].resolveOpen({ toc: A_TOC });

  await expectTheChapterFallback(screen);
});

test('a heading that links nowhere is never the fallback', async () => {
  const { screen } = await aJump();

  readers[0].resolveOpen({
    toc: [{ href: '#', type: '', title: 'On Memory', children: [A_TOC[1]] }],
  });

  await expectTheChapterFallback(screen);
});

const HIGHLIGHT_LOCATOR_PATH = '/api/v1/highlights/:highlightId/locator';

/** The shell opened at a chapter of the book, counting what it asks the server on the way. */
const aChapterJump = async (chapter: ChapterWithHighlights) => {
  worker.use(...readiumApi());
  worker.use(...bookApi({ book: aBookDetails({ chapters: [chapter] }) }).handlers);
  const asked: string[] = [];
  // Answering nothing passes each request on to the handler that answers it.
  worker.use(
    http.get(POSITION_PATH, () => {
      asked.push('resume');
    }),
    http.get(HIGHLIGHT_LOCATOR_PATH, () => {
      asked.push('locator');
    })
  );
  const screen = await renderShell({ target: { kind: 'chapter', id: chapter.id } });
  await expect.poll(() => readers.length).toBe(1);
  return Object.assign(screen, { asked: () => asked });
};

test("a chapter jump opens the book at that chapter's place in the contents", async () => {
  const screen = await aChapterJump(aChapter({ id: 11, name: 'On Memory' }));

  expect(readers[0].openedWith[0].initialLocation).toBeUndefined();
  readers[0].resolveOpen({ toc: A_TOC });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([THE_START_OF_ON_MEMORY]);
  // The book's own contents answer a chapter jump, so the server is asked nothing.
  expect(screen.asked()).toEqual([]);
  // Arriving at the chapter is what was asked for, not a miss to apologise for.
  await expectNoApology(screen);
});

test('a part whose heading links nowhere opens at its first section', async () => {
  const screen = await aChapterJump(aChapter({ id: 11, name: 'Part two' }));

  readers[0].resolveOpen({ toc: A_TOC_OF_PARTS });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([THE_START_OF_PART_TWO]);
  await expectNoApology(screen);
});

test("a chapter this edition's contents do not name opens at the start, and says so", async () => {
  const screen = await aChapterJump(aChapter({ id: 11, name: 'On Forgetting' }));

  readers[0].resolveOpen({ toc: A_TOC });

  await expectOnScreen(screen);
  expect(readers[0].goToCalls).toEqual([]);
  await expectToBeTold(screen, CHAPTER_NOT_IN_THE_BOOK);
});

/**
 * On a phone the two arrow gutters were most of the screen and the book was a
 * strip down the middle, while the buttons themselves sat over the page they
 * turn. Swiping is the gesture at hand there — Readium's own column snapper
 * handles it inside the publication's frame — so the buttons go and the page
 * takes the width back. The chrome above the page, which fits either way,
 * stays exactly as it was.
 */
test('the page-turn buttons stand aside on a phone and come back on a wider screen', async () => {
  worker.use(...readiumApi());
  const screen = await anOpenBook();

  await page.viewport(PHONE_VIEWPORT.width, PHONE_VIEWPORT.height);

  // Out of the accessibility tree, not merely out of sight: a `display: none`
  // button is one no pointer, screen reader or tab stop can reach.
  await expect.poll(() => screen.getByRole('button', { name: 'Next page' }).query()).toBeNull();
  expect(screen.getByRole('button', { name: 'Previous page' }).query()).toBeNull();
  await expect.element(screen.getByRole('button', { name: 'Contents' })).toBeVisible();

  await page.viewport(DEFAULT_VIEWPORT.width, DEFAULT_VIEWPORT.height);

  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Previous page' })).toBeVisible();
});

/**
 * A book's highlights are drawn on its pages wherever the server could place
 * them, in the colour of their labels.
 */
const aYellowHighlight = () => aHighlight({ id: 300, label: { ui_color: '#F59E0B' } });

/** The book's details with these highlights in its one chapter. */
const aBookHolding = (highlights: Highlight[]) =>
  bookApi({ book: aBookDetails({ chapters: [aChapter({ highlights })] }) });

/** The shell open over a book whose highlights the server answers for with these places. */
const aBookWithHighlights = async (
  highlights: Highlight[],
  locators: HighlightLocatorResponse[] = highlights.map((highlight) =>
    aHighlightLocator(highlight.id)
  )
) => {
  worker.use(...readiumApi());
  worker.use(...highlightLocatorsApi(locators));
  worker.use(...aBookHolding(highlights).handlers);
  return await anOpenBook();
};

/** The set the engine was last given. */
const lastSubmitted = (): EbookDecoration[] | undefined => {
  const { decorations } = readers[0];
  return decorations[decorations.length - 1];
};

const drawnTints = () => lastSubmitted()?.map((decoration) => decoration.tint);

const drawnIds = () => lastSubmitted()?.map((decoration) => decoration.id);

test("a highlight is drawn at its place, in its label's colour", async () => {
  await aBookWithHighlights([aYellowHighlight()]);

  await expect.poll(lastSubmitted).toEqual([
    {
      id: 'highlight-300',
      location: {
        href: 'resources/OEBPS/chapter1.xhtml',
        type: 'application/xhtml+xml',
        locations: { progression: 0, cssSelector: 'p' },
        text: { highlight: 'rarest and purest' },
      },
      tint: '#F59E0B',
      opacity: 0.35,
    },
  ]);
});

test('a highlight with no label is drawn in the default colour', async () => {
  await aBookWithHighlights([aHighlight({ id: 300 })]);

  await expect.poll(drawnTints).toEqual([DEFAULT_LABEL_COLOR]);
});

test('a label colour stored without its hash is still drawn in it', async () => {
  await aBookWithHighlights([aHighlight({ id: 300, label: { ui_color: 'F59E0B' } })]);

  await expect.poll(drawnTints).toEqual(['#F59E0B']);
});

test('a label colour that is not six hex digits is drawn in the default', async () => {
  // Shorthand a person editing by hand would write, and a colour to any browser,
  // but not to the engine, which reads its channels two digits at a time.
  await aBookWithHighlights([aHighlight({ id: 300, label: { ui_color: '#fa0' } })]);

  await expect.poll(drawnTints).toEqual([DEFAULT_LABEL_COLOR]);
});

test('a highlight the server could not place is not drawn, and the one beside it is', async () => {
  await aBookWithHighlights(
    [aYellowHighlight(), aHighlight({ id: 301 })],
    [aHighlightLocator(300), anUnplacedHighlight(301)]
  );

  await expect.poll(drawnIds).toEqual(['highlight-300']);
});

test('a place listed for a highlight the book no longer has is not drawn', async () => {
  await aBookWithHighlights([aYellowHighlight()], [aHighlightLocator(300), aHighlightLocator(301)]);

  await expect.poll(drawnIds).toEqual(['highlight-300']);
});

test('the book is on screen before its highlights are placed', async () => {
  worker.use(...readiumApi());
  worker.use(...highlightLocatorsApi([aHighlightLocator(300)], { delayMs: 1_500 }));
  worker.use(...aBookHolding([aYellowHighlight()]).handlers);

  await anOpenBook();
  expect(lastSubmitted()).toEqual([]);

  await expect.poll(drawnIds, { timeout: 3_000 }).toEqual(['highlight-300']);
  expect(readers).toHaveLength(1);
});

test('a highlight whose label changes is redrawn by the same reader', async () => {
  worker.use(...readiumApi());
  worker.use(...highlightLocatorsApi([aHighlightLocator(300)]));
  worker.use(...aBookHolding([aYellowHighlight()]).handlers);
  const screen = await anOpenBook();
  await expect.poll(drawnTints).toEqual(['#F59E0B']);

  // A relabelling done elsewhere in the app ends with the book's details
  // refetched into the cache, and the cache is what reaches the open reader.
  screen.queryClient.setQueryData(
    getGetBookDetailsQueryKey(1),
    aBookDetails({
      chapters: [
        aChapter({ highlights: [aHighlight({ id: 300, label: { ui_color: '#3B82F6' } })] }),
      ],
    })
  );

  await expect.poll(drawnTints).toEqual(['#3B82F6']);
  expect(readers).toHaveLength(1);
});

test('turning a page leaves the drawn highlights alone', async () => {
  const screen = await aBookWithHighlights([aYellowHighlight()]);
  await expect.poll(drawnIds).toEqual(['highlight-300']);
  const submissions = readers[0].decorations.length;

  readers[0].reportLocation(aFakeLocation(2));

  await expect.element(screen.getByText('50%', { exact: true })).toBeVisible();
  expect(readers[0].decorations).toHaveLength(submissions);
});

test('activating a decoration asks to open its highlight', async () => {
  worker.use(...readiumApi());
  const opened: number[] = [];
  const screen = await anOpenBook({}, { onOpenHighlight: (id) => opened.push(id) });

  readers[0].activateDecoration('highlight-300');
  expect(opened).toEqual([300]);

  await screen.rerenderShell({ onOpenHighlight: (id) => opened.push(id * 10) });
  readers[0].activateDecoration('highlight-300');

  expect(opened).toEqual([300, 3000]);
  expect(readers).toHaveLength(1);
});

/** Words well inside the viewport, so the popover has room below them. */
const A_SELECTION = {
  location: { ...aFakeLocation(1), text: { highlight: 'rarest and purest' } },
  rect: { x: 400, y: 300, width: 200, height: 20 },
  shownAsSelected: true,
};

const theSelectionToolbar = () => page.getByRole('toolbar', { name: 'Selected text' });

test('a selection in the book shows the popover below it', async () => {
  worker.use(...readiumApi());
  await anOpenBook();

  readers[0].select(A_SELECTION);

  await expect.element(theSelectionToolbar()).toBeVisible();
  const selectionBottom = A_SELECTION.rect.y + A_SELECTION.rect.height;
  await expect
    .poll(() => theSelectionToolbar().element().getBoundingClientRect().top)
    .toBeGreaterThanOrEqual(selectionBottom);
  const { x, y, width, height } = theSelectionToolbar().element().getBoundingClientRect();
  const onTop = document.elementFromPoint(x + width / 2, y + height / 2);
  expect(theSelectionToolbar().element().contains(onTop)).toBe(true);
});

/** The shell with the book on screen and the popover up over a selection in it. */
const aBookWithASelection = async (props: Partial<ReaderShellProps> = {}) => {
  worker.use(...readiumApi());
  const screen = await anOpenBook({}, props);
  readers[0].select(A_SELECTION);
  await expect.element(theSelectionToolbar()).toBeVisible();
  return screen;
};

const pressCancel = () => theSelectionToolbar().getByRole('button', { name: 'Cancel' }).click();

test('pressing on the popover leaves focus where it was', async () => {
  const screen = await aBookWithASelection();
  const focused = screen.getByRole('button', { name: 'Close reader' }).element() as HTMLElement;
  focused.focus();

  await pressCancel();

  expect(document.activeElement).toBe(focused);
});

test('cancel lets the selection go', async () => {
  await aBookWithASelection();

  await pressCancel();

  expect(readers[0].clearSelectionCalls).toBe(1);
  await expect.element(theSelectionToolbar()).not.toBeInTheDocument();
});

test('a selection let go in the book closes the popover', async () => {
  await aBookWithASelection();

  readers[0].select(null);

  await expect.element(theSelectionToolbar()).not.toBeInTheDocument();
});

test('a page turn while something is selected lets it go', async () => {
  await aBookWithASelection();

  readers[0].reportLocation(aFakeLocation(2));

  expect(readers[0].clearSelectionCalls).toBe(1);
  await expect.element(theSelectionToolbar()).not.toBeInTheDocument();
});

const pressHighlight = () =>
  theSelectionToolbar().getByRole('button', { name: 'Highlight' }).click();

const standIns = () =>
  (lastSubmitted() ?? []).filter((decoration) => decoration.id.startsWith('selection-'));

const standInWords = () => standIns().map((decoration) => decoration.location.text?.highlight);

test('pressing Highlight lets go of the selection and draws it at once', async () => {
  const { handlers, bodies } = highlightCreationApi([{ status: 500, delayMs: 300 }]);
  worker.use(...handlers);
  await aBookWithASelection();

  await pressHighlight();

  expect(readers[0].clearSelectionCalls).toBe(1);
  await expect.element(theSelectionToolbar()).not.toBeInTheDocument();
  await expect.poll(standIns).toEqual([
    {
      id: 'selection-1',
      location: A_SELECTION.location,
      tint: '#F59E0B',
      opacity: 0.35,
    },
  ]);
  await expect.poll(() => bodies.length).toBe(1);
  expect(bodies[0].device_color).toBe('yellow');
});

test('a highlight is stamped with the time on the reader’s own clock', async () => {
  const { handlers, bodies } = highlightCreationApi([{ status: 500, delayMs: 300 }]);
  worker.use(...handlers);
  await aBookWithASelection();
  const before = DateTime.now();

  await pressHighlight();

  await expect.poll(() => bodies.length).toBe(1);
  const madeAt = DateTime.fromISO(bodies[0].datetime, { setZone: true });
  expect(madeAt.toFormat('ZZ')).toBe(before.toFormat('ZZ'));
  expect(madeAt.diff(before).as('seconds')).toBeGreaterThanOrEqual(0);
  expect(madeAt.diff(before).as('seconds')).toBeLessThan(5);
});

/** The nine colours KOReader offers, in the order the popover puts them in. */
const KOREADER_COLORS = [
  'Yellow',
  'Orange',
  'Red',
  'Purple',
  'Blue',
  'Cyan',
  'Green',
  'Olive',
  'Gray',
];

/** The dropdown saying which colour Highlight will use. */
const theColorChoice = () =>
  theSelectionToolbar().getByRole('combobox', { name: 'Highlight colour' });

/** The colours the opened dropdown offers, in the order it offers them. */
const colorOptions = () =>
  page
    .getByRole('option')
    .elements()
    .map((option) => option.textContent.trim());

const chooseColor = async (name: string) => {
  await theColorChoice().click();
  await page.getByRole('option', { name }).click();
};

/** The book's labels, over `bookApi`'s empty list, which MSW resolves newest first. */
const bookLabels = (...items: Partial<HighlightLabelInBook>[]) =>
  http.get('/api/v1/books/:bookId/highlight-labels', () =>
    HttpResponse.json({
      items: items.map((item, index) => ({
        id: 10 + index,
        label_source: 'book',
        highlight_count: 3,
        ...item,
      })),
    })
  );

const toolbarButtonNames = () =>
  Array.from(
    theSelectionToolbar().element().querySelectorAll('button, [role="button"]'),
    (button) => button.textContent.trim()
  );

test("the popover highlights in KOReader's own yellow until another colour is chosen", async () => {
  await aBookWithASelection();

  await expect.element(theColorChoice()).toHaveTextContent('Yellow');
  expect(toolbarButtonNames()).toEqual(['Highlight', 'Extend', 'Cancel']);
});

test('the dropdown offers the nine colours KOReader knows', async () => {
  await aBookWithASelection();

  await theColorChoice().click();

  await expect.poll(colorOptions).toEqual(KOREADER_COLORS);
});

/**
 * The dropdown keeps focus off itself for a pointer, which is what keeps the
 * selection drawn; a reader who has tabbed to it gets the menu MUI gives
 * everyone -- open on Enter, walk it with the arrows, Escape to leave it.
 */
test('the dropdown opens, walks and closes from the keyboard', async () => {
  await aBookWithASelection();
  (theColorChoice().element() as HTMLElement).focus();

  await userEvent.keyboard('{Enter}');
  await expect.poll(colorOptions).toEqual(KOREADER_COLORS);
  await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}');

  await expect.element(theColorChoice()).toHaveTextContent('Red');
  // Polled rather than read: the menu takes its closing transition to go.
  await expect.poll(() => colorOptions().length).toBe(0);

  await userEvent.keyboard('{Enter}');
  await expect.poll(colorOptions).toEqual(KOREADER_COLORS);
  await userEvent.keyboard('{Escape}');

  await expect.poll(() => colorOptions().length).toBe(0);
});

test('choosing a colour marks it without making a highlight', async () => {
  const { handlers, bodies } = highlightCreationApi([{ status: 500, delayMs: 300 }]);
  worker.use(...handlers);
  await aBookWithASelection();

  await chooseColor('Green');

  await expect.element(theColorChoice()).toHaveTextContent('Green');
  await sleep(100);
  expect(bodies).toEqual([]);
  expect(standIns()).toEqual([]);
  expect(readers[0].clearSelectionCalls).toBe(0);
  await expect.element(theSelectionToolbar()).toBeVisible();
});

test('choosing a colour leaves focus where it was and the selection where it is', async () => {
  const screen = await aBookWithASelection();
  const focused = screen.getByRole('button', { name: 'Close reader' }).element() as HTMLElement;
  focused.focus();

  await chooseColor('Green');

  expect(document.activeElement).toBe(focused);
  expect(readers[0].clearSelectionCalls).toBe(0);
});

const standInTints = () => standIns().map((decoration) => decoration.tint);

test('Highlight stores the passage in the chosen colour and draws it in that hue', async () => {
  const { handlers, bodies } = highlightCreationApi([{ status: 500, delayMs: 300 }]);
  worker.use(...handlers);
  await aBookWithASelection();
  await chooseColor('Green');

  await pressHighlight();

  expect(readers[0].clearSelectionCalls).toBe(1);
  await expect.poll(standInTints).toEqual(['#10B981']);
  await expect.poll(() => bodies.length).toBe(1);
  expect(bodies[0].device_color).toBe('green');
});

test('choosing a colour stores it as the one to offer next', async () => {
  await aBookWithASelection();

  await chooseColor('Green');

  expect(storedPreferences()?.highlightColor).toBe('green');
});

/**
 * The colour is stored beside the appearance without being part of one, and the
 * engine reflows the whole book for any appearance it is handed again.
 */
test('choosing a colour does not lay the book out again', async () => {
  await aBookWithASelection();
  const laidOutTimes = readers[0].appearances.length;

  await chooseColor('Green');

  await expect.element(theColorChoice()).toHaveTextContent('Green');
  expect(readers[0].appearances).toHaveLength(laidOutTimes);
});

test('the colour left in storage is the one the popover highlights in', async () => {
  const { handlers, bodies } = highlightCreationApi([{ status: 500, delayMs: 300 }]);
  worker.use(...handlers);
  seedPreferences({ ...A_STORED_APPEARANCE, highlightColor: 'blue' });
  await aBookWithASelection();
  await expect.element(theColorChoice()).toHaveTextContent('Blue');

  await pressHighlight();

  await expect.poll(() => bodies.length).toBe(1);
  expect(bodies[0].device_color).toBe('blue');
});

test('a colour the book has labelled wears the label', async () => {
  const { handlers, bodies } = highlightCreationApi([{ status: 500, delayMs: 300 }]);
  worker.use(
    ...handlers,
    bookLabels({
      device_color: 'yellow',
      device_style: 'lighten',
      label: 'Important',
      ui_color: '#ff0000',
    })
  );
  await aBookWithASelection();
  await expect.element(theColorChoice()).toHaveTextContent('Important');
  await theColorChoice().click();
  await expect.poll(colorOptions).toEqual(['Important', ...KOREADER_COLORS.slice(1)]);

  await page.getByRole('option', { name: 'Important' }).click();
  await pressHighlight();

  await expect.poll(standInTints).toEqual(['#ff0000']);
  await expect.poll(() => bodies.length).toBe(1);
  expect(bodies[0].device_color).toBe('yellow');
});

test("a label on another drawer of a colour is not that colour's", async () => {
  worker.use(
    bookLabels(
      { device_color: 'yellow', device_style: 'underscore', label: 'Vocabulary' },
      // Its own colour's label, so the list is known to have arrived.
      { device_color: 'blue', device_style: 'lighten', label: 'Later' }
    )
  );
  await aBookWithASelection();

  await theColorChoice().click();

  await expect
    .poll(colorOptions)
    .toEqual(KOREADER_COLORS.map((name) => (name === 'Blue' ? 'Later' : name)));
});

/** About as long a label as a reader types, and far longer than the row is wide. */
const A_LONG_LABEL = 'Worth coming back to on a second reading';

/** Words a narrow screen has room for, so only the row's own width is in question. */
const A_NARROW_SELECTION = { ...A_SELECTION, rect: { x: 40, y: 300, width: 120, height: 20 } };

test('a label longer than the row keeps the popover inside a narrow phone', async () => {
  worker.use(
    ...readiumApi(),
    bookLabels({ device_color: 'yellow', device_style: 'lighten', label: A_LONG_LABEL })
  );
  await page.viewport(NARROW_VIEWPORT.width, NARROW_VIEWPORT.height);
  await anOpenBook();

  readers[0].select(A_NARROW_SELECTION);

  await expect.element(theColorChoice()).toHaveTextContent(A_LONG_LABEL);
  await expect
    .poll(() => theSelectionToolbar().element().getBoundingClientRect().right)
    .toBeLessThanOrEqual(window.innerWidth);
  expect(document.documentElement.scrollWidth).toBe(window.innerWidth);
});

test.each([
  [503, "The book's file couldn't be read, so the highlight wasn't saved."],
  [500, 'Failed to save the highlight. Please try again.'],
])('a highlight the server answers %i to is taken back, and says why', async (status, message) => {
  worker.use(...highlightCreationApi([{ status, delayMs: 300 }]).handlers);
  const screen = await aBookWithASelection();

  await pressHighlight();

  await expect.poll(standInWords).toEqual(['rarest and purest']);
  await expectToBeTold(screen, message);
  await expect.poll(standInWords).toEqual([]);
});

test('tapping a highlight still being saved opens nothing', async () => {
  worker.use(...highlightCreationApi([{ status: 500, delayMs: 300 }]).handlers);
  const opened: number[] = [];
  await aBookWithASelection({ onOpenHighlight: (id) => opened.push(id) });
  await pressHighlight();
  await expect.poll(() => standIns().length).toBe(1);

  readers[0].activateDecoration(standIns()[0].id);

  expect(opened).toEqual([]);
  await expect.poll(standIns).toEqual([]);
});

test('two highlights made before either is answered are each settled on their own', async () => {
  worker.use(
    ...highlightCreationApi([
      { status: 422, delayMs: 200 },
      { id: 400, delayMs: 800 },
    ]).handlers
  );
  const screen = await aBookWithASelection();
  worker.use(...highlightLocatorApi([aHighlightLocator(400)]));
  await pressHighlight();
  readers[0].select({
    ...A_SELECTION,
    location: { ...aFakeLocation(1), text: { highlight: 'form of generosity' } },
  });
  await pressHighlight();
  await expect.poll(standInWords).toEqual(['rarest and purest', 'form of generosity']);

  await expectToBeTold(screen, 'Try selecting a little more text.');
  expect(standInWords()).toEqual(['form of generosity']);

  await expect.poll(standInWords).toEqual([]);
  expect(screen.getByRole('alert').filter({ hasText: 'Failed' }).query()).toBeNull();
});

test('a saved highlight the server cannot place raises no error', async () => {
  worker.use(...highlightCreationApi([{ id: 400, delayMs: 300 }]).handlers);
  const screen = await aBookWithASelection();
  worker.use(...highlightLocatorApi([]));
  await pressHighlight();
  await expect.poll(() => standIns().length).toBe(1);

  await expect.poll(standIns).toEqual([]);
  expect(screen.getByRole('alert').elements()).toEqual([]);
});

const pressExtend = () => theSelectionToolbar().getByRole('button', { name: 'Extend' }).click();

const theExtensionBar = () => page.getByRole('group', { name: 'Extending the highlight' });

/** The book with the words selected carried over to a tap yet to come. */
const aSelectionBeingExtended = async () => {
  const screen = await aBookWithASelection();
  await pressExtend();
  await expect.element(theExtensionBar()).toBeVisible();
  return screen;
};

test('Extend asks the engine for one and says what to do next', async () => {
  await aBookWithASelection();

  await pressExtend();

  expect(readers[0].startSelectionExtensionCalls).toBe(1);
  await expect.element(theExtensionBar()).toHaveTextContent('Tap where the highlight ends');
  await expect.element(theSelectionToolbar()).not.toBeInTheDocument();
});

test('the way out of an extension lets the engine forget where the passage started', async () => {
  await aSelectionBeingExtended();

  await theExtensionBar().getByRole('button', { name: 'Cancel' }).click();

  expect(readers[0].cancelSelectionExtensionCalls).toBe(1);
  await expect.element(theExtensionBar()).not.toBeInTheDocument();
});

test('the passage an extension ends on comes back under the popover', async () => {
  worker.use(...highlightCreationApi([{ status: 500, delayMs: 300 }]).handlers);
  await aSelectionBeingExtended();

  readers[0].select({
    ...A_SELECTION,
    location: { ...aFakeLocation(1), text: { highlight: 'rarest and purest form of generosity' } },
  });

  await expect.element(theExtensionBar()).not.toBeInTheDocument();
  await expect.element(theSelectionToolbar()).toBeVisible();
  await pressHighlight();

  await expect.poll(standInWords).toEqual(['rarest and purest form of generosity']);
});

test('a tap the engine cannot extend says a highlight stays inside one chapter', async () => {
  const screen = await aSelectionBeingExtended();

  readers[0].refuseSelectionExtension();

  await expectToBeTold(screen, 'A highlight has to stay inside one chapter.');
  await expect.element(theExtensionBar()).toBeVisible();
});

test('closing the reader while an extension waits leaves nothing behind', async () => {
  const screen = await aSelectionBeingExtended();

  screen.unmount();

  expect(theExtensionBar().query()).toBeNull();
  expect(readers[0].cancelSelectionExtensionCalls).toBe(0);
  await expect.poll(() => readers[0].destroyed).toBe(true);
});

test('a passage the browser no longer shows as selected is drawn, and Highlight stores it', async () => {
  worker.use(...highlightCreationApi([{ status: 500, delayMs: 300 }]).handlers);
  await aBookWithASelection();

  readers[0].select({ ...A_SELECTION, shownAsSelected: false });

  await expect.poll(drawnIds).toEqual(['held-passage']);
  await expect.element(theSelectionToolbar()).toBeVisible();

  await pressHighlight();

  expect(readers[0].clearSelectionCalls).toBe(1);
  await expect.poll(standInWords).toEqual(['rarest and purest']);
  await expect.poll(drawnIds).toEqual(['selection-1']);
});

/** Highlight 400 stored and placed when made, over the handlers given, with a selection up. */
const aSelectionOverTheDetails = async (...handlers: Parameters<typeof worker.use>) => {
  worker.use(...readiumApi());
  const details = bookApi();
  worker.use(...details.handlers);
  worker.use(...highlightLocatorApi([aHighlightLocator(400)]));
  const storeIt = (id: number) => {
    details.state.book = aBookDetails({
      chapters: [aChapter({ highlights: [aHighlight({ id })] })],
    });
  };
  worker.use(...highlightCreationApi([{ id: 400 }], { onCreated: storeIt }).handlers);
  worker.use(...handlers);
  await renderShell();
  await expect.poll(() => readers.length).toBe(1);
  readers[0].resolveOpen();
  readers[0].select(A_SELECTION);
};

test('a saved highlight takes over from what was drawn for it with nothing missing between', async () => {
  // Late, so a stand-in let go before the details are in leaves sets with nothing drawn.
  await aSelectionOverTheDetails(
    http.get(BOOK_DETAILS_PATH, () => delay(300).then(() => undefined))
  );
  const submittedBefore = readers[0].decorations.length;

  await pressHighlight();

  await expect.poll(drawnIds).toEqual(['highlight-400']);
  const handedOver = readers[0].decorations.slice(submittedBefore);
  const drawsNeither = handedOver.filter(
    (set) => !set.some(({ id }) => id === 'highlight-400' || id.startsWith('selection-'))
  );
  expect(handedOver.length).toBeGreaterThan(1);
  expect(drawsNeither).toEqual([]);
});

test('a highlight made while the placed highlights are still loading is drawn', async () => {
  await aSelectionOverTheDetails(...highlightLocatorsApi([], { delayMs: 1_500 }));

  await pressHighlight();

  await expect.poll(drawnIds, { timeout: 5_000 }).toContain('highlight-400');
});
