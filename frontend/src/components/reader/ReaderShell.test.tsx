import { ReaderShell, type ReaderShellProps } from '@/components/reader/ReaderShell.tsx';
import { FakeEbookReader, aFakeLocation } from '@tests/fakes/FakeEbookReader';
import { readiumApi } from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { HttpResponse, delay, http } from 'msw';
import { beforeEach, expect, test } from 'vitest';
import { render } from 'vitest-browser-react';

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
    <ReaderShell
      bookId={1}
      title="The Pragmatic Reader"
      onClose={() => {}}
      createReader={createReader}
      {...props}
    />
  );

type Screen = Awaited<ReturnType<typeof renderShell>>;

/** The shell with the book on screen at its first page. */
const anOpenBook = async () => {
  const screen = await renderShell();
  await expect.poll(() => readers.length).toBe(1);
  readers[0].resolveOpen();
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
  expect(readers[0].openedWith).toEqual([MANIFEST_URL]);
  await expect.element(screen.getByLabelText('Loading the book')).toBeVisible();
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

test('closing the shell destroys the reader', async () => {
  worker.use(...readiumApi());

  const screen = await anOpenBook();
  screen.unmount();

  await expect.poll(() => readers[0].destroyed).toBe(true);
});
