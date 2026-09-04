import { aBookDetails } from '@tests/fixtures/book';
import { aBookActivity, aBookStatistics, aReadingSession } from '@tests/fixtures/sessions';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';

/**
 * The statistics tab, over an API serving `state`.
 *
 * `alsoHandle` goes in through a `use` call of its own, after the happy path.
 * Within a single call MSW gives the earlier argument precedence, so passing
 * both together would let `bookApi`'s handler shadow the override rather than
 * the other way round.
 */
const renderStatisticsTab = async (
  state: Parameters<typeof bookApi>[0] = {},
  ...alsoHandle: Parameters<typeof worker.use>
) => {
  const { handlers } = bookApi({ book: aBookDetails(), ...state });
  worker.use(...handlers);
  if (alsoHandle.length > 0) {
    worker.use(...alsoHandle);
  }

  return renderApp({ path: '/book/1/statistics' });
};

const statisticsFails = http.get(
  '/api/v1/books/:bookId/statistics',
  () => new HttpResponse(null, { status: 500 })
);

const oneSession = { sessions: [aReadingSession({ id: 200 })] };

test('a session card headlines the session and lists its pages and duration', async () => {
  const screen = await renderStatisticsTab(oneSession);

  // The headline's date and time are rendered in the browser's own locale, so
  // only its shape is asserted here; the two facts below are locale-free.
  await expect.element(screen.getByRole('heading', { name: /^Session / })).toBeVisible();
  await expect.element(screen.getByText('Pages 102 – 115')).toBeVisible();
  await expect.element(screen.getByText('Duration 1h 11m')).toBeVisible();
});

test('a session without a page range still shows its duration', async () => {
  const screen = await renderStatisticsTab({
    sessions: [aReadingSession({ id: 200, start_page: null, end_page: null })],
  });

  await expect.element(screen.getByText('Duration 1h 11m')).toBeVisible();
  expect(screen.getByText(/^Pages /).elements()).toHaveLength(0);
});

test('the sessions tab reports having no sessions', async () => {
  const screen = await renderStatisticsTab({ sessions: [] });

  await expect.element(screen.getByText('No reading sessions recorded yet.')).toBeVisible();
});

test('the tab pages five sessions at a time', async () => {
  const screen = await renderStatisticsTab({
    sessions: Array.from({ length: 5 }, (_, index) => aReadingSession({ id: 200 + index })),
    sessionTotal: 7,
  });

  await expect.element(screen.getByRole('heading', { name: /^Session / }).first()).toBeVisible();
  expect(screen.getByRole('heading', { name: /^Session / }).elements()).toHaveLength(5);

  // 7 sessions over a page of 5: a second page, and no third.
  await expect.element(screen.getByRole('button', { name: 'Go to page 2' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Go to page 3' }).elements()).toHaveLength(0);
});

test('the tab summarises the reading above the list', async () => {
  const screen = await renderStatisticsTab({ ...oneSession, statistics: aBookStatistics() });

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

test('a book nobody has opened summarises itself at zero', async () => {
  const screen = await renderStatisticsTab({ sessions: [] });

  await expect.element(screen.getByText('No reading sessions recorded yet.')).toBeVisible();
  // Zeroes rather than a missing summary: a section that disappears reads as
  // a page that failed to load.
  await expect.element(screen.getByText('Time read')).toBeVisible();
  await expect.element(screen.getByText('0m')).toBeVisible();
  await expect.element(screen.getByText('Sessions').first()).toBeVisible();
  await expect
    .element(screen.getByRole('progressbar', { name: 'Reading progress' }))
    .toHaveAttribute('aria-valuenow', '0');
  // Nothing was measured, so nothing is claimed about what a session is like.
  expect(screen.getByText('Average session').elements()).toHaveLength(0);
  expect(screen.getByText('Reading span').elements()).toHaveLength(0);
});

test('a book with no recorded position summarises the sessions without a progress bar', async () => {
  const screen = await renderStatisticsTab({
    ...oneSession,
    statistics: aBookStatistics({ progress_percent: null }),
  });

  await expect.element(screen.getByText('8h 25m')).toBeVisible();
  expect(screen.getByRole('progressbar', { name: 'Reading progress' }).elements()).toHaveLength(0);
});

test('a failed summary reports itself and leaves the sessions listed', async () => {
  const screen = await renderStatisticsTab(oneSession, statisticsFails);

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Failed to load reading statistics.' }))
    .toBeVisible();
  await expect.element(screen.getByText('Pages 102 – 115')).toBeVisible();
  expect(screen.getByText('Time read').elements()).toHaveLength(0);
});

test('the activity grid draws the whole window, not only the days that were read', async () => {
  const screen = await renderStatisticsTab({ ...oneSession, statistics: aBookStatistics() });

  await expect.element(screen.getByRole('img', { name: /pages on / }).first()).toBeVisible();

  // The API sends three days and the window's two ends; every day between them
  // is the client's to fill, so a 365-day window must draw 365 squares.
  expect(screen.getByRole('img', { name: /pages on / }).elements()).toHaveLength(365);
});

test('every square says what its day came to, tooltip or not', async () => {
  const screen = await renderStatisticsTab({ ...oneSession, statistics: aBookStatistics() });

  // The dates are rendered in the browser's own locale, so each label is
  // matched by the count that opens it. A phone cannot hover a tooltip, so
  // this label is the only way to the number there.
  await expect.element(screen.getByRole('img', { name: /^60 pages on / })).toBeVisible();
  await expect.element(screen.getByRole('img', { name: /^10 pages on / })).toBeVisible();
  // A day nobody read is a square all the same, and says so.
  expect(screen.getByRole('img', { name: /^0 pages on / }).elements()).toHaveLength(362);
});

test('the grid says what its squares count and what darker means', async () => {
  const screen = await renderStatisticsTab({ ...oneSession, statistics: aBookStatistics() });

  // The window's months are rendered in the browser's own locale, so only the
  // unit that follows them is asserted here.
  await expect.element(screen.getByText(/· pages read$/)).toBeVisible();
  await expect.element(screen.getByText('Less')).toBeVisible();
  await expect.element(screen.getByText('More')).toBeVisible();
});

test('a book synced without page numbers has its grid measured in minutes', async () => {
  const screen = await renderStatisticsTab({
    ...oneSession,
    statistics: aBookStatistics({ activity: aBookActivity({ unit: 'minutes' }) }),
  });

  await expect.element(screen.getByText(/· minutes read$/)).toBeVisible();
});

test('a book with nothing to plot draws the year empty', async () => {
  const screen = await renderStatisticsTab({ sessions: [] });

  await expect
    .element(screen.getByRole('img', { name: /^Nothing read on / }).first())
    .toBeVisible();
  expect(screen.getByRole('img', { name: /^Nothing read on / }).elements()).toHaveLength(365);
  // Nothing was read, so there is no scale from less to more to explain.
  await expect.element(screen.getByText(/· nothing read yet$/)).toBeVisible();
  expect(screen.getByText('Less').elements()).toHaveLength(0);
});

test('a failed statistics request leaves the grid off the page entirely', async () => {
  const screen = await renderStatisticsTab(oneSession, statisticsFails);

  // The snackbar reports the failure once; a grid claiming an empty year
  // would be a second, and a false, account of the same thing.
  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Failed to load reading statistics.' }))
    .toBeVisible();
  expect(screen.getByRole('img', { name: / on / }).elements()).toHaveLength(0);
  expect(screen.getByRole('img', { name: /^Nothing read on / }).elements()).toHaveLength(0);
});
