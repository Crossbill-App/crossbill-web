import type { RecentCapture } from '@/api/generated/model';
import { aReadingActivity, aReadingSummary } from '@tests/fixtures/activity';
import { aBookCard } from '@tests/fixtures/book';
import { aCapturedHighlight, aCapturedNote } from '@tests/fixtures/captures';
import { renderApp } from '@tests/harness/renderApp';
import { libraryApi } from '@tests/msw/libraryApi';
import { worker } from '@tests/msw/worker';
import { DateTime } from 'luxon';
import { expect, test } from 'vitest';

/** Days named against the browser's clock, because the feed's day marks are. */
const today = DateTime.now().toFormat('yyyy-MM-dd');
const yesterday = DateTime.now().minus({ days: 1 }).toFormat('yyyy-MM-dd');

const EMMA = { id: 1, title: 'Emma' };
const DUNE = { id: 2, title: 'Dune' };
const ULYSSES = { id: 3, title: 'Ulysses' };
const HAMLET = { id: 4, title: 'Hamlet' };

/** A dashboard whose capture feed holds `captures` and whose grid is empty. */
const aFeedOf = (captures: RecentCapture[]) =>
  libraryApi([], [aBookCard({ title: 'Emma' })], null, null, captures);

/** A dashboard whose activity grid has one day on it, made of `book_ids`. */
const aDayOfReading = (book_ids: number[], books: { id: number; title: string }[]) =>
  libraryApi(
    [],
    [aBookCard({ title: 'Emma' })],
    aReadingActivity({
      days: [{ date: '2026-03-01', value: 40, level: 3, book_ids }],
      books,
    })
  );

test('a day says how much was read and which books it was spent on', async () => {
  worker.use(...aDayOfReading([EMMA.id, DUNE.id], [EMMA, DUNE]));

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByRole('img', { name: /^40 pages on .+ — Emma, Dune$/ }))
    .toBeVisible();
});

test('a day spent grazing counts the books it does not name', async () => {
  worker.use(
    ...aDayOfReading([EMMA.id, DUNE.id, ULYSSES.id, HAMLET.id], [EMMA, DUNE, ULYSSES, HAMLET])
  );

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByRole('img', { name: /Emma, Dune, Ulysses and 1 more$/ }))
    .toBeVisible();
});

test('the numbers beside the grid say what the year adds up to', async () => {
  worker.use(
    ...libraryApi(
      [],
      [aBookCard({ title: 'Emma' })],
      aReadingActivity({
        days: [{ date: '2026-03-01', value: 40, level: 3, book_ids: [EMMA.id] }],
      }),
      aReadingSummary({
        // Named against the browser's clock, because that is the clock the
        // reader's "today" is decided on.
        last_read: DateTime.now().toFormat('yyyy-MM-dd'),
        seconds_today: 25 * 60,
        streak_days: 4,
        days_read: 137,
        books_read: 42,
      })
    )
  );

  const screen = await renderApp({ path: '/' });

  await expect.element(screen.getByText('25m')).toBeVisible();
  await expect.element(screen.getByText('Today', { exact: true })).toBeVisible();
  await expect.element(screen.getByText('4 days')).toBeVisible();
  await expect.element(screen.getByText('137')).toBeVisible();
  await expect.element(screen.getByText('42')).toBeVisible();
});

test('a reader with nothing on the grid is shown no grid', async () => {
  worker.use(...libraryApi([], [aBookCard({ title: 'Emma' })]));

  const screen = await renderApp({ path: '/' });

  // Polled rather than read once: the section is on screen with its spinner
  // until the request answers, and only then takes itself off.
  await expect
    .element(screen.getByRole('heading', { name: 'Reading activity' }))
    .not.toBeInTheDocument();
});

test('the capture feed cuts the newest highlights and notes into days', async () => {
  worker.use(
    ...libraryApi([], [aBookCard({ title: 'Emma' })], null, null, [
      aCapturedHighlight({
        text: 'A reader who never disagrees has not finished reading.',
        day: today,
        captured_at: `${today}T20:00:00`,
      }),
      aCapturedNote({
        title: 'Koskela',
        day: yesterday,
        captured_at: `${yesterday}T19:05:00`,
      }),
    ])
  );

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByText('A reader who never disagrees has not finished reading.'))
    .toBeVisible();
  await expect.element(screen.getByRole('heading', { name: 'Today' })).toBeVisible();
  await expect.element(screen.getByRole('heading', { name: 'Yesterday' })).toBeVisible();
  await expect.element(screen.getByText('Koskela')).toBeVisible();
  await expect.element(screen.getByText('Character')).toBeVisible();
});

test('a capture opens the book page at the highlight it names', async () => {
  worker.use(
    ...aFeedOf([aCapturedHighlight({ id: 7, book_id: 3, text: 'The map is not the territory.' })])
  );

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByRole('link', { name: /The map is not the territory/ }))
    .toHaveAttribute('href', '/book/3/highlights?highlightId=7');
});

test('a day the cap trimmed says how much of that book it left out', async () => {
  worker.use(
    ...aFeedOf([aCapturedHighlight({ book_id: 3, book_title: 'Bullshit Jobs', more_in_book: 5 })])
  );

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByRole('link', { name: '+5 more in Bullshit Jobs that day' }))
    .toHaveAttribute('href', '/book/3/highlights?from=2026-08-30&to=2026-08-30');
});

test('a reader who has captured nothing is shown no feed', async () => {
  worker.use(...aFeedOf([]));

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByRole('heading', { name: 'Recent highlights and notes' }))
    .not.toBeInTheDocument();
});
