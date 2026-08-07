import { aBookDetails, aChapter } from '@tests/fixtures/book';
import { aDigestHit } from '@tests/fixtures/semantic';
import { renderApp } from '@tests/harness/renderApp';
import { settingsWithEmbeddings } from '@tests/msw/auth';
import { bookApi } from '@tests/msw/bookApi';
import { semanticSearchApi } from '@tests/msw/semanticSearchApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const SEARCH_PLACEHOLDER = 'Search chapters by meaning…';

/** Two parts, one leaf chapter each — enough to prove ancestors survive. */
const aStructuredBook = () =>
  aBookDetails({
    chapters: [
      aChapter({ id: 10, name: 'Part One', chapter_number: 1 }),
      aChapter({ id: 11, name: 'Attention and memory', chapter_number: 2, parent_id: 10 }),
      aChapter({ id: 20, name: 'Part Two', chapter_number: 3 }),
      aChapter({ id: 21, name: 'Roman roads', chapter_number: 4, parent_id: 20 }),
    ],
  });

test('searching narrows the chapter tree to matches and their parents', async () => {
  worker.use(
    settingsWithEmbeddings(true),
    ...semanticSearchApi({
      attention: {
        digests: [
          aDigestHit({ chapter_id: 11, chapter_name: 'Attention and memory', score: 0.72 }),
        ],
      },
    }),
    ...bookApi({ book: aStructuredBook() }).handlers
  );

  const screen = await renderApp({ path: '/book/1/structure' });
  await expect.element(screen.getByText('Roman roads')).toBeVisible();

  await userEvent.fill(screen.getByPlaceholder(SEARCH_PLACEHOLDER), 'attention');

  // The non-matching branch disappearing is what proves the search landed.
  await expect.element(screen.getByText('Roman roads')).not.toBeInTheDocument();
  await expect.element(screen.getByText('Attention and memory')).toBeVisible();
  await expect.element(screen.getByText('Part One')).toBeVisible();
  expect(screen.getByText('Part Two').elements()).toHaveLength(0);

  // Clearing restores the whole tree.
  await userEvent.fill(screen.getByPlaceholder(SEARCH_PLACEHOLDER), '');
  await expect.element(screen.getByText('Roman roads')).toBeVisible();
  await expect.element(screen.getByText('Part Two')).toBeVisible();
});

test('a match below the score cutoff counts as no match', async () => {
  worker.use(
    settingsWithEmbeddings(true),
    ...semanticSearchApi({
      quantum: {
        digests: [
          aDigestHit({ chapter_id: 11, chapter_name: 'Attention and memory', score: 0.12 }),
        ],
      },
    }),
    ...bookApi({ book: aStructuredBook() }).handlers
  );

  const screen = await renderApp({ path: '/book/1/structure' });
  await userEvent.fill(screen.getByPlaceholder(SEARCH_PLACEHOLDER), 'quantum');

  await expect.element(screen.getByText(/No chapters match/)).toBeVisible();
  expect(screen.getByText('Attention and memory').elements()).toHaveLength(0);
});
