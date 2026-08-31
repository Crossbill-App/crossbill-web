import { aBookDetails } from '@tests/fixtures/book';
import { aBookStatistics, aReadingSession } from '@tests/fixtures/sessions';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';

test('a session card headlines the session and lists its pages and duration', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    sessions: [aReadingSession({ id: 200 })],
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/sessions' });

  // The headline's date and time are rendered in the browser's own locale, so
  // only its shape is asserted here; the two facts below are locale-free.
  await expect.element(screen.getByRole('heading', { name: /^Session / })).toBeVisible();
  await expect.element(screen.getByText('Pages 102 – 115')).toBeVisible();
  await expect.element(screen.getByText('Duration 1h 11m')).toBeVisible();
});

test('a session without a page range still shows its duration', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    sessions: [aReadingSession({ id: 200, start_page: null, end_page: null })],
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/sessions' });

  await expect.element(screen.getByText('Duration 1h 11m')).toBeVisible();
  expect(screen.getByText(/^Pages /).elements()).toHaveLength(0);
});

test('the sessions tab reports having no sessions', async () => {
  const { handlers } = bookApi({ book: aBookDetails(), sessions: [] });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/sessions' });

  await expect.element(screen.getByText('No reading sessions recorded yet.')).toBeVisible();
});

test('the tab pages five sessions at a time', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    sessions: Array.from({ length: 5 }, (_, index) => aReadingSession({ id: 200 + index })),
    sessionTotal: 7,
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/sessions' });

  await expect.element(screen.getByRole('heading', { name: /^Session / }).first()).toBeVisible();
  expect(screen.getByRole('heading', { name: /^Session / }).elements()).toHaveLength(5);

  // 7 sessions over a page of 5: a second page, and no third.
  await expect.element(screen.getByRole('button', { name: 'Go to page 2' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Go to page 3' }).elements()).toHaveLength(0);
});

test('the tab summarises the reading above the list', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    sessions: [aReadingSession({ id: 200 })],
    statistics: aBookStatistics(),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/sessions' });

  await expect.element(screen.getByText('63%')).toBeVisible();
  await expect
    .element(screen.getByRole('progressbar', { name: 'Reading progress' }))
    .toHaveAttribute('aria-valuenow', '63');
  await expect.element(screen.getByText('8h 25m')).toBeVisible();
  await expect.element(screen.getByText('42m')).toBeVisible();
  await expect.element(screen.getByText('42 days')).toBeVisible();
  // The book's stats strip above the tabs says "Last read <date>" too, so this
  // one is matched exactly rather than by substring.
  await expect.element(screen.getByText('Last read', { exact: true })).toBeVisible();
});

test('the summary stays away until the book has been read', async () => {
  const { handlers } = bookApi({ book: aBookDetails(), sessions: [] });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/sessions' });

  await expect.element(screen.getByText('No reading sessions recorded yet.')).toBeVisible();
  // The list keeps its own heading; only the summary above it stands down.
  await expect.element(screen.getByRole('heading', { name: 'Sessions' })).toBeVisible();
  expect(screen.getByText('Time read').elements()).toHaveLength(0);
});

test('a book with no recorded position summarises the sessions without a progress bar', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    sessions: [aReadingSession({ id: 200 })],
    statistics: aBookStatistics({ progress_percent: null }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/sessions' });

  await expect.element(screen.getByText('8h 25m')).toBeVisible();
  expect(screen.getByRole('progressbar', { name: 'Reading progress' }).elements()).toHaveLength(0);
});

test('a failed summary reports itself and leaves the sessions listed', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    sessions: [aReadingSession({ id: 200 })],
    statistics: aBookStatistics(),
  });
  worker.use(...handlers);
  // Registered last, so it takes precedence over the happy-path GET above.
  worker.use(
    http.get('/api/v1/books/:bookId/statistics', () => new HttpResponse(null, { status: 500 }))
  );

  const screen = await renderApp({ path: '/book/1/sessions' });

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Failed to load reading statistics.' }))
    .toBeVisible();
  await expect.element(screen.getByText('Pages 102 – 115')).toBeVisible();
  expect(screen.getByText('Time read').elements()).toHaveLength(0);
});
