import { aReadingActivity } from '@tests/fixtures/activity';
import { aBookCard } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { libraryApi } from '@tests/msw/libraryApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';

const EMMA = { id: 1, title: 'Emma' };
const DUNE = { id: 2, title: 'Dune' };
const ULYSSES = { id: 3, title: 'Ulysses' };
const HAMLET = { id: 4, title: 'Hamlet' };

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

test('a reader with nothing on the grid is shown no grid', async () => {
  worker.use(...libraryApi([], [aBookCard({ title: 'Emma' })]));

  const screen = await renderApp({ path: '/' });

  // Polled rather than read once: the section is on screen with its spinner
  // until the request answers, and only then takes itself off.
  await expect
    .element(screen.getByRole('heading', { name: 'Reading activity' }))
    .not.toBeInTheDocument();
});
