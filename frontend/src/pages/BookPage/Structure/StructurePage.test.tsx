import { aBookDetails, aChapter } from '@tests/fixtures/book';
import { aChapterDigest, aDigestQuestion } from '@tests/fixtures/digest';
import { aDigestHit } from '@tests/fixtures/semantic';
import { renderApp } from '@tests/harness/renderApp';
import { settingsWithAi, settingsWithEmbeddings } from '@tests/msw/auth';
import { bookApi } from '@tests/msw/bookApi';
import { semanticSearchApi } from '@tests/msw/semanticSearchApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const SEARCH_PLACEHOLDER = 'Search chapters by meaning...';

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

/**
 * A parent row has two jobs, so it splits: the title opens the chapter, the
 * chevron (and the rest of the row) works the children list. Each must leave
 * the other alone.
 */
test('a parent chapter opens from its title, and expands from its chevron', async () => {
  worker.use(...bookApi({ book: aStructuredBook() }).handlers);

  const screen = await renderApp({ path: '/book/1/structure' });
  await expect.element(screen.getByText('Part One')).toBeVisible();

  await userEvent.click(screen.getByRole('button', { name: 'Collapse Part One' }));
  await expect.element(screen.getByText('Attention and memory')).not.toBeInTheDocument();
  expect(screen.getByRole('dialog').elements()).toHaveLength(0);

  await userEvent.click(screen.getByRole('button', { name: 'Expand Part One' }));
  await expect.element(screen.getByText('Attention and memory')).toBeVisible();

  await userEvent.click(screen.getByText('Part One'));

  await expect
    .element(screen.getByRole('dialog').getByRole('tab', { name: 'Questions' }))
    .toBeVisible();
  // The title must not double as a toggle: the branch stays open behind it.
  await expect.element(screen.getByText('Attention and memory')).toBeInTheDocument();
});

/**
 * The case a related-content link hits: parents are digested and embedded like
 * any other chapter, so a semantic result can address one directly. While the
 * dialog resolved against leaves only, that URL rendered nothing at all — no
 * dialog, no error, the search param simply unread.
 */
test('a link straight to a parent chapter opens its dialog', async () => {
  worker.use(...bookApi({ book: aStructuredBook() }).handlers);

  const screen = await renderApp({ path: '/book/1/structure?chapterId=10' });

  await expect
    .element(screen.getByRole('dialog').getByRole('tab', { name: 'Questions' }))
    .toBeVisible();
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

/**
 * A chapter dialog lives in a search param, and closes itself with
 * `history.back()`. The router renders that popstate like any other
 * navigation, which means scrolling to the top of the page unless it is
 * restoring the position the entry was left at (`scrollRestoration`) — so the
 * page under a dismissed dialog used to jump back to the first chapter.
 */
test('closing a chapter dialog leaves the page where it was scrolled to', async () => {
  worker.use(
    ...bookApi({
      book: aBookDetails({
        chapters: Array.from({ length: 40 }, (_, index) =>
          aChapter({ id: 100 + index, name: `Chapter ${index + 1}`, chapter_number: index + 1 })
        ),
      }),
    }).handlers
  );

  const screen = await renderApp({ path: '/book/1/structure' });
  await expect.element(screen.getByText('Chapter 40')).toBeVisible();

  window.scrollTo(0, 600);
  expect(window.scrollY).toBe(600);

  await userEvent.click(screen.getByText('Chapter 10'));
  await expect
    .element(screen.getByRole('dialog').getByRole('tab', { name: 'Questions' }))
    .toBeVisible();

  // Where the dialog's body-scroll lock parked the page, read rather than
  // assumed to be 600: driving a real click scrolls its target into view
  // first, which can move the page a little.
  const parked = -Number.parseFloat(document.body.style.top);
  expect(parked).toBeGreaterThan(0);

  await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
  await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();

  // Settled rather than polled: the regression restored the position and then
  // scrolled away from it a frame later, which a poll would call a pass.
  await new Promise((resolve) => setTimeout(resolve, 400));
  expect(window.scrollY).toBe(parked);
});

/**
 * A digest answer saves itself when the field is left, with nothing else on
 * screen to say so — the reader had no way to know their answer was stored.
 */
test('a digest answer says it saved when the field is left', async () => {
  worker.use(
    settingsWithAi(true),
    ...bookApi({
      book: aStructuredBook(),
      digests: [
        aChapterDigest({
          chapter_id: 11,
          questions: [aDigestQuestion({ question: 'What makes attention a filter?' })],
        }),
      ],
    }).handlers
  );

  const screen = await renderApp({ path: '/book/1/structure' });
  await userEvent.click(screen.getByText('Attention and memory'));

  const dialog = screen.getByRole('dialog');
  const answer = dialog.getByPlaceholder('Write your answer...');
  await expect.element(answer).toBeVisible();
  expect(dialog.getByText('Saved').elements()).toHaveLength(0);

  // The marker's space is reserved, so appearing must not push what is under
  // it. Measured as the gap between the field and the next control rather than
  // an absolute position, which the dialog's own scrolling would move.
  const gapBelowField = () =>
    dialog.getByRole('button', { name: 'Quiz me' }).element().getBoundingClientRect().top -
    answer.element().getBoundingClientRect().bottom;
  const restingGap = gapBelowField();

  await userEvent.fill(answer, 'It drops what is not attended to.');
  await userEvent.click(dialog.getByText('What makes attention a filter?'));

  await expect.element(dialog.getByText('Saved')).toBeVisible();
  expect(gapBelowField()).toBe(restingGap);

  // And it clears itself again — the marker fades out rather than sticking.
  await expect.element(dialog.getByText('Saved')).not.toBeInTheDocument();
  expect(gapBelowField()).toBe(restingGap);
});
