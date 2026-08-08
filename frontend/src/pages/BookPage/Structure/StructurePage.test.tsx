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

/**
 * The structure tab of a book where "attention" matches chapter 11 only,
 * rendered and settled — "Roman roads" on screen is the unfiltered tree.
 */
const renderStructureWithAttentionMatch = async () => {
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
  return screen;
};

test('searching narrows the chapter tree to matches and their parents', async () => {
  const screen = await renderStructureWithAttentionMatch();

  // The field searches on Enter, not per keystroke.
  await userEvent.fill(screen.getByPlaceholder(SEARCH_PLACEHOLDER), 'attention');
  await userEvent.keyboard('{Enter}');

  // The non-matching branch disappearing is what proves the search landed.
  await expect.element(screen.getByText('Roman roads')).not.toBeInTheDocument();
  await expect.element(screen.getByText('Attention and memory')).toBeVisible();
  await expect.element(screen.getByText('Part One')).toBeVisible();
  expect(screen.getByText('Part Two').elements()).toHaveLength(0);

  // Clearing restores the whole tree.
  await userEvent.fill(screen.getByPlaceholder(SEARCH_PLACEHOLDER), '');
  await userEvent.keyboard('{Enter}');
  await expect.element(screen.getByText('Roman roads')).toBeVisible();
  await expect.element(screen.getByText('Part Two')).toBeVisible();
});

test('leaving the search field runs the search without pressing Enter', async () => {
  const screen = await renderStructureWithAttentionMatch();

  await userEvent.fill(screen.getByPlaceholder(SEARCH_PLACEHOLDER), 'attention');
  await userEvent.tab();

  await expect.element(screen.getByText('Roman roads')).not.toBeInTheDocument();
  await expect.element(screen.getByText('Attention and memory')).toBeVisible();
});

/**
 * Three levels deep, with a reading position that makes "Part Two" the true
 * current chapter (read, and its next top-level sibling "Part Three" is not).
 * "Deep Topic" sits two levels under "Part One" (10 > 11 > 12), so a search
 * that matches only it must still expand both ancestors to reveal it.
 */
const aBookWithReadingPosition = () =>
  aBookDetails({
    reading_position: { index: 5, char_index: 0 },
    chapters: [
      aChapter({
        id: 10,
        name: 'Part One',
        chapter_number: 1,
        start_position: { index: 0, char_index: 0 },
      }),
      aChapter({
        id: 11,
        name: 'Overview',
        chapter_number: 2,
        parent_id: 10,
        start_position: { index: 1, char_index: 0 },
      }),
      aChapter({
        id: 12,
        name: 'Deep Topic',
        chapter_number: 3,
        parent_id: 11,
        start_position: { index: 2, char_index: 0 },
      }),
      aChapter({
        id: 20,
        name: 'Part Two',
        chapter_number: 4,
        start_position: { index: 5, char_index: 0 },
      }),
      aChapter({
        id: 21,
        name: 'Section X',
        chapter_number: 5,
        parent_id: 20,
        start_position: { index: 6, char_index: 0 },
      }),
      aChapter({
        id: 30,
        name: 'Part Three',
        chapter_number: 6,
        start_position: { index: 10, char_index: 0 },
      }),
    ],
  });

test('a search reveals a deeply-nested match and leaves the current-chapter indicator on the true current chapter', async () => {
  worker.use(
    settingsWithEmbeddings(true),
    ...semanticSearchApi({
      deep: {
        digests: [
          aDigestHit({ chapter_id: 12, chapter_name: 'Deep Topic', score: 0.5 }),
          // Scored above "Deep Topic" so the top level re-sorts to [Part Two,
          // Part One] — the opposite of document order, which is what would
          // fool an index-based "next sibling" current-chapter check.
          aDigestHit({ chapter_id: 20, chapter_name: 'Part Two', score: 0.9 }),
        ],
      },
    }),
    ...bookApi({ book: aBookWithReadingPosition() }).handlers
  );

  const screen = await renderApp({ path: '/book/1/structure' });
  await expect.element(screen.getByText('Part Three')).toBeVisible();

  await userEvent.fill(screen.getByPlaceholder(SEARCH_PLACEHOLDER), 'deep');
  await userEvent.keyboard('{Enter}');

  // The non-matching top-level chapter disappearing is what proves the
  // search landed before the assertions below are trusted.
  await expect.element(screen.getByText('Part Three')).not.toBeInTheDocument();

  // Finding 2: a match two levels down (10 > 11 > 12) stays reachable —
  // both ancestor accordions must have expanded, not just the top one.
  await expect.element(screen.getByText('Deep Topic')).toBeVisible();

  // Finding 1: "Part Two" is current in document order regardless of how
  // the search re-sorts the top level; "Part One" is merely read.
  await expect
    .element(screen.getByRole('img', { name: 'Part Two: Current chapter' }))
    .toBeVisible();
  await expect.element(screen.getByRole('img', { name: 'Part One: Read chapter' })).toBeVisible();
  expect(screen.getByRole('img', { name: 'Part One: Current chapter' }).elements()).toHaveLength(0);
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
  await userEvent.keyboard('{Enter}');

  await expect.element(screen.getByText(/No chapters match/)).toBeVisible();
  expect(screen.getByText('Attention and memory').elements()).toHaveLength(0);
});
