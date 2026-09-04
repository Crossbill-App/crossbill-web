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

test('a reader with nothing on the grid is shown the year empty', async () => {
  worker.use(...libraryApi([], [aBookCard({ title: 'Emma' })]));

  const screen = await renderApp({ path: '/' });

  await expect.element(screen.getByText(/^No reading recorded yet\./)).toBeVisible();

  // A year of uncoloured squares rather than no grid: the section says what
  // will fill it instead of leaving a heading out of the dashboard.
  expect(screen.getByRole('img', { name: /^Nothing read on / }).elements()).toHaveLength(365);
});

test('an empty grid counts nothing beside it', async () => {
  worker.use(...libraryApi([], [aBookCard({ title: 'Emma' })]));

  const screen = await renderApp({ path: '/' });

  await expect.element(screen.getByRole('heading', { name: 'Reading activity' })).toBeVisible();
  // The numbers wait until there is something to count; a row of zeroes is
  // not what a new reader should meet first.
  expect(screen.getByText('Days read').elements()).toHaveLength(0);
  expect(screen.getByText('Current streak').elements()).toHaveLength(0);
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

test("a note's leftovers point at the book's notes, not at its highlights", async () => {
  worker.use(
    ...aFeedOf([aCapturedNote({ book_id: 3, book_title: 'Bullshit Jobs', more_in_book: 2 })])
  );

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByRole('link', { name: '+2 more in Bullshit Jobs that day' }))
    .toHaveAttribute('href', '/book/3/notes');
});

test("a note's body is read as the markdown it is", async () => {
  worker.use(...aFeedOf([aCapturedNote({ text: 'The **first** programmer.' })]));

  const screen = await renderApp({ path: '/' });

  // In a tag of its own: rendered as source, the asterisks would be around it.
  const emphasised = screen.getByText('first');
  await expect.element(emphasised).toBeVisible();
  expect(emphasised.element().tagName).toBe('STRONG');
});

test('a reader who has captured nothing is told what will fill the feed', async () => {
  worker.use(...aFeedOf([]));

  const screen = await renderApp({ path: '/' });

  await expect
    .element(screen.getByRole('heading', { name: 'Recent highlights and notes' }))
    .toBeVisible();
  await expect.element(screen.getByText(/^No highlights or notes yet\./)).toBeVisible();
});

test('a first-time reader gets every section, each saying what will fill it', async () => {
  worker.use(...libraryApi([], []));

  const screen = await renderApp({ path: '/' });

  await expect.element(screen.getByText(/^No books yet\./)).toBeVisible();
  await expect.element(screen.getByText(/^No reading recorded yet\./)).toBeVisible();
  await expect.element(screen.getByText(/^No highlights or notes yet\./)).toBeVisible();
  for (const section of ['Recent books', 'Reading activity', 'Recent highlights and notes']) {
    await expect.element(screen.getByRole('heading', { name: section })).toBeVisible();
  }
});
