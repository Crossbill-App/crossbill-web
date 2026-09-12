import { aBookDetails } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { readiumApi } from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';

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
  worker.use(
    http.post(
      '/api/v1/readium/books/:bookId/session',
      () => new HttpResponse(null, { status: 500 })
    )
  );

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
