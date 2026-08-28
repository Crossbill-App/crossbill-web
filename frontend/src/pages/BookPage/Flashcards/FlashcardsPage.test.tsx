import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';
import { page } from 'vitest/browser';

const QUESTION = 'What did the cartographer mistake the map for, in the end, and why did it matter?';

/** A card with a linked note, so the row carries all three action icons. */
const aBookWithLinkedFlashcard = () =>
  aBookDetails({
    chapters: [
      aChapter({
        highlights: [
          aHighlight({
            flashcards: [
              {
                id: 700,
                user_id: 1,
                book_id: 1,
                highlight_id: 300,
                note_id: 100,
                question: QUESTION,
                answer: 'The territory.',
              },
            ],
          }),
        ],
      }),
    ],
  });

/**
 * The action icons sit in the flow beside the question, not floating over it:
 * a fixed reserve on the text could not cover a three-icon cluster, so on a
 * narrow row the icons landed on the question and on its collapse chevron.
 * Measured against the whole toggle, whose rightmost content is the chevron.
 */
test('a flashcard row keeps its actions clear of the question at any width', async () => {
  worker.use(...bookApi({ book: aBookWithLinkedFlashcard() }).handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  await expect.element(screen.getByText(QUESTION)).toBeVisible();

  for (const width of [1440, 380]) {
    await page.viewport(width, 800);

    const toggle = screen
      .getByRole('button', { name: QUESTION })
      .element()
      .getBoundingClientRect();
    const viewNote = screen
      .getByRole('button', { name: 'View linked note' })
      .element()
      .getBoundingClientRect();

    expect(toggle.width).toBeGreaterThan(0);
    expect(toggle.right).toBeLessThanOrEqual(viewNote.left);
  }
});
