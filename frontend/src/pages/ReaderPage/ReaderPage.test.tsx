import { aBookDetails } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { noPublication, readiumApi } from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { delay, http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const MANIFEST_PATH = '/api/v1/readium/books/:bookId/manifest.json';
const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const RESOURCE_PATH = '/api/v1/readium/books/:bookId/resources/*';

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
  await expect.element(screen.getByText('Page 1 of 2')).toBeVisible();
  return screen;
};

const expectPage = (screen: Screen, label: string) =>
  expect.element(screen.getByText(label), { timeout: 5_000 }).toBeVisible();

test('the book header offers to open the book in the reader', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1' });
  await screen.getByRole('link', { name: 'Open in reader' }).click();

  await expectTheReaderOpen(screen);
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

test('the next button turns the page and the label follows', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectPage(screen, 'Page 2 of 2');

  await screen.getByRole('button', { name: 'Previous page' }).click();
  await expectPage(screen, 'Page 1 of 2');
});

test('the arrow keys turn the page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();

  await userEvent.keyboard('{ArrowRight}');
  await expectPage(screen, 'Page 2 of 2');

  await userEvent.keyboard('{ArrowLeft}');
  await expectPage(screen, 'Page 1 of 2');
});

test('an arrow key pressed before the book is on screen does not jam it', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  // The chapter alone is late; everything else is served as usual by falling
  // through to the handler registered underneath this one.
  worker.use(
    http.get(RESOURCE_PATH, async ({ params }) => {
      if (String(params[0]) !== 'OEBPS/chapter1.xhtml') return;
      await delay(1_500);
    })
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByLabelText('Loading the book')).toBeVisible();
  await userEvent.keyboard('{ArrowRight}');

  await expectPage(screen, 'Page 1 of 2');
  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectPage(screen, 'Page 2 of 2');
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
  worker.use(http.post(SESSION_PATH, () => HttpResponse.json({ expires_in: 900 })));
  worker.use(http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 500 })));

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(screen.getByText('The book could not be opened. Please try again later.'))
    .toBeVisible();

  worker.use(...readiumApi());
  await screen.getByRole('button', { name: 'Try again' }).click();

  await expectPage(screen, 'Page 1 of 2');
});

test('a lapsed session holds the book until it has been renewed', async () => {
  worker.use(...aReadableBook());
  // One second of life, so the cookie has genuinely lapsed by the time the tab
  // is brought back. The scheduled renewal cannot interfere: its floor is five.
  worker.use(...readiumApi({ expiresIn: 1 }));

  const screen = await openTheBook();

  worker.use(
    http.post(SESSION_PATH, async () => {
      await delay(2_000);
      return HttpResponse.json({ expires_in: 900 });
    })
  );
  await new Promise((resolve) => setTimeout(resolve, 1_200));
  window.dispatchEvent(new Event('focus'));

  await expect.element(screen.getByText('Reconnecting…')).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();

  await expect
    .element(screen.getByText('Reconnecting…'), { timeout: 5_000 })
    .not.toBeInTheDocument();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
});
