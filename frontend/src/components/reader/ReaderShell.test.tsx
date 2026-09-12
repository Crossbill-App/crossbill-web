import type { EbookTocEntry, OpenedEbook } from '@/components/reader/EbookReader.ts';
import { ReaderShell, type ReaderShellProps } from '@/components/reader/ReaderShell.tsx';
import { theme } from '@/theme/theme.ts';
import { ThemeProvider } from '@mui/material/styles';
import { FakeEbookReader, aFakeLocation } from '@tests/fakes/FakeEbookReader';
import { readiumApi } from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { HttpResponse, delay, http } from 'msw';
import { beforeEach, expect, test } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const RESOURCE_PATH = '/api/v1/readium/books/:bookId/resources/*';
const MANIFEST_URL = `${window.location.origin}/api/v1/readium/books/1/manifest.json`;

const readers: FakeEbookReader[] = [];

const createReader = () => {
  const reader = new FakeEbookReader();
  readers.push(reader);
  return reader;
};

beforeEach(() => {
  readers.length = 0;
});

const aSlowSession = (ms: number) =>
  http.post(SESSION_PATH, async () => {
    await delay(ms);
    return HttpResponse.json({ expires_in: 900 });
  });

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const renderShell = async (props: Partial<ReaderShellProps> = {}) =>
  await render(
    <ThemeProvider theme={theme}>
      <ReaderShell
        bookId={1}
        title="The Pragmatic Reader"
        onClose={() => {}}
        createReader={createReader}
        {...props}
      />
    </ThemeProvider>
  );

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
const anOpenBook = async (opened: Partial<OpenedEbook> = {}) => {
  const screen = await renderShell();
  await expect.poll(() => readers.length).toBe(1);
  readers[0].resolveOpen(opened);
  await expect.element(screen.getByText('Page 1 of 2')).toBeVisible();
  return screen;
};

const expectReconnecting = (screen: Screen) =>
  expect.element(screen.getByText('Reconnecting…')).toBeVisible();

test('the shell waits for the cookie before opening the book', async () => {
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
    textAlign: null,
    columnCount: 1,
    // The light page is the app's own off-white rather than publisher white.
    pageBackgroundColor: theme.palette.background.default,
    pageTextColor: theme.palette.text.primary,
  });
});

test('a book whose positions say nothing about progress still numbers its pages', async () => {
  worker.use(...readiumApi());

  const screen = await anOpenBook();

  await expect.element(screen.getByText('Page 1 of 2', { exact: true })).toBeVisible();
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

test('a book that never appears times out and can be retried', async () => {
  worker.use(...readiumApi());

  const screen = await renderShell({ bootTimeoutMs: 300 });

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
  await expect.element(screen.getByText('Page 2 of 2')).toBeVisible();
});

test('a book whose chapters never arrive times out and can be retried', async () => {
  worker.use(...readiumApi());
  worker.use(http.get(RESOURCE_PATH, () => delay('infinite')));

  const screen = await renderShell({ createReader: undefined, bootTimeoutMs: 500 });

  await expect
    .element(screen.getByText('This book could not be opened in the reader.'), { timeout: 3_000 })
    .toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Try again' })).toBeVisible();

  worker.use(...readiumApi());
  await screen.getByRole('button', { name: 'Try again' }).click();

  await expect.element(screen.getByText('Page 1 of 2'), { timeout: 5_000 }).toBeVisible();
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

test('a line height chosen in the popover reaches the engine', async () => {
  const screen = await anOpenAppearance();

  await screen.getByRole('button', { name: 'Tight' }).click();

  expect(readers[0].appearances.map((appearance) => appearance.lineHeight)).toEqual([1.2]);
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
