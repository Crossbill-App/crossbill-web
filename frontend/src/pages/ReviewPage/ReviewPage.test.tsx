import type { DueFlashcard, FlashcardReviewRequestRating } from '@/api/generated/model';
import { aDueFlashcard } from '@tests/fixtures/review';
import { saveFlashcardDialog } from '@tests/harness/flashcardDialog';
import { renderApp } from '@tests/harness/renderApp';
import { afterTheAnswersRender } from '@tests/harness/settle';
import { reviewApi } from '@tests/msw/reviewApi';
import { worker } from '@tests/msw/worker';
import { range } from 'lodash';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

const FIRST = aDueFlashcard({ id: 701, question: 'What is attention', answer: 'A filter' });
const SECOND = aDueFlashcard({ id: 702, question: 'What is memory', answer: 'A store' });

const cardsNumbered = (count: number, overrides: Partial<DueFlashcard> = {}) =>
  range(count).map((index) =>
    aDueFlashcard({
      id: 1000 + index,
      question: `Question ${index + 1}`,
      answer: `Answer ${index + 1}`,
      ...overrides,
    })
  );

const startReview = async (cards: DueFlashcard[], path = '/review') => {
  const api = reviewApi({ cards });
  worker.use(...api.handlers);
  const screen = await renderApp({ path });
  return { screen, state: api.state };
};

const expectCardShown = async (screen: Screen, card: DueFlashcard) => {
  await expect.element(screen.getByText(card.question)).toBeVisible();
};

const showAnswer = async (screen: Screen) => {
  await userEvent.click(screen.getByRole('button', { name: 'Show answer' }));
};

const gradeButton = (screen: Screen, label: string) =>
  screen.getByRole('button', { name: new RegExp(`^${label}`) });

const expectAllCaughtUp = async (screen: Screen) => {
  await expect.element(screen.getByRole('status')).toBeVisible();
};

const expectAlertRaised = async (screen: Screen) => {
  await expect.element(screen.getByRole('alert')).toBeVisible();
};

test.each<[string, FlashcardReviewRequestRating]>([
  ['Again', 'again'],
  ['Hard', 'hard'],
  ['Good', 'good'],
  ['Easy', 'easy'],
])('%s sends its rating and shows the next card', async (label, rating) => {
  const { screen, state } = await startReview([FIRST, SECOND]);
  await expectCardShown(screen, FIRST);
  await expect.element(screen.getByText('1 of 2')).toBeVisible();

  await showAnswer(screen);
  await userEvent.click(gradeButton(screen, label));

  await expectCardShown(screen, SECOND);
  await expect.element(screen.getByText('2 of 2')).toBeVisible();
  await expect.poll(() => state.reviews).toEqual([{ flashcardId: FIRST.id, rating }]);
});

test('each grade shows when the card would be due again', async () => {
  const { screen } = await startReview([FIRST]);

  await showAnswer(screen);

  for (const name of ['Again 8h', 'Hard 1d', 'Good 3d', 'Easy 2mo']) {
    await expect.element(screen.getByRole('button', { name })).toBeVisible();
  }
});

test('the answer and its source stay hidden until shown', async () => {
  const { screen } = await startReview([FIRST]);
  await expectCardShown(screen, FIRST);
  await expect.element(screen.getByText(FIRST.book_title, { exact: false })).toBeVisible();
  expect(screen.getByText(FIRST.answer).elements()).toHaveLength(0);
  expect(screen.getByText(FIRST.highlight_text ?? '').elements()).toHaveLength(0);

  await showAnswer(screen);

  await expect.element(screen.getByText(FIRST.answer)).toBeVisible();
  await expect.element(screen.getByText(FIRST.highlight_text ?? '')).toBeVisible();
});

test.each([
  ['Space', ' '],
  ['Enter', '{Enter}'],
])('%s shows the answer', async (_name, key) => {
  const { screen } = await startReview([FIRST]);
  await expectCardShown(screen, FIRST);

  await userEvent.keyboard(key);

  await expect.element(screen.getByText(FIRST.answer)).toBeVisible();
});

test('keys 1 to 4 grade a shown answer as again, hard, good and easy', async () => {
  const cards = cardsNumbered(4);
  const { screen, state } = await startReview(cards);

  for (const [index, key] of ['1', '2', '3', '4'].entries()) {
    await expectCardShown(screen, cards[index]);
    await userEvent.keyboard(' ');
    await expect.element(screen.getByText(cards[index].answer)).toBeVisible();
    await userEvent.keyboard(key);
  }

  await expectAllCaughtUp(screen);
  await expect
    .poll(() => state.reviews.map((review) => review.rating))
    .toEqual(['again', 'hard', 'good', 'easy']);
});

test('a grade key does nothing before the answer is shown', async () => {
  const { screen, state } = await startReview([FIRST, SECOND]);
  await expectCardShown(screen, FIRST);

  await userEvent.keyboard('3');
  await afterTheAnswersRender(screen.queryClient);

  await expectCardShown(screen, FIRST);
  expect(state.reviews).toEqual([]);
});

test('a grade that fails to save keeps the card on screen', async () => {
  const { screen } = await startReview([FIRST, SECOND]);
  worker.use(
    http.post('/api/v1/flashcards/:flashcardId/reviews', () =>
      HttpResponse.json(null, { status: 500 })
    )
  );
  await expectCardShown(screen, FIRST);

  await showAnswer(screen);
  await userEvent.click(gradeButton(screen, 'Good'));

  await expectAlertRaised(screen);
  await expectCardShown(screen, FIRST);
  await expect.element(screen.getByText('1 of 2')).toBeVisible();
});

test('a card that left review elsewhere is skipped when graded', async () => {
  const { screen } = await startReview([FIRST, SECOND]);
  worker.use(
    http.post('/api/v1/flashcards/:flashcardId/reviews', () =>
      HttpResponse.json(null, { status: 409 })
    )
  );
  await expectCardShown(screen, FIRST);

  await showAnswer(screen);
  await userEvent.click(gradeButton(screen, 'Good'));

  await expectAlertRaised(screen);
  await expectCardShown(screen, SECOND);
});

test('suspending moves on, and undo puts the card back', async () => {
  const { screen, state } = await startReview([FIRST, SECOND]);
  await expectCardShown(screen, FIRST);

  await userEvent.click(screen.getByRole('button', { name: 'Suspend' }));

  await expectCardShown(screen, SECOND);
  await expect.poll(() => state.cards[0].status).toBe('suspended');

  await userEvent.click(screen.getByRole('button', { name: 'Undo' }));

  await expectCardShown(screen, FIRST);
  await expect.element(screen.getByText('1 of 2')).toBeVisible();
  await expect.poll(() => state.cards[0].status).toBe('active');
});

test('Space after suspending with the mouse shows the next answer', async () => {
  const { screen, state } = await startReview([FIRST, SECOND]);
  await expectCardShown(screen, FIRST);

  await userEvent.click(screen.getByRole('button', { name: 'Suspend' }));
  await expectCardShown(screen, SECOND);
  await userEvent.keyboard(' ');

  await expect.element(screen.getByText(SECOND.answer)).toBeVisible();
  await expect.poll(() => state.cards.map((card) => card.status)).toEqual(['suspended', 'active']);
});

test('editing keeps the card on screen, ungraded', async () => {
  const { screen, state } = await startReview([FIRST, SECOND]);
  await expectCardShown(screen, FIRST);
  await showAnswer(screen);

  await userEvent.click(screen.getByRole('button', { name: 'Edit', exact: true }));
  await saveFlashcardDialog(screen, 'Edit flashcard', { question: 'What does attention do' });

  await expect.element(screen.getByText('What does attention do')).toBeVisible();
  await expect.element(screen.getByText(FIRST.answer)).toBeVisible();
  await expect.element(screen.getByText('1 of 2')).toBeVisible();
  expect(state.reviews).toEqual([]);
});

test('deleting from the edit dialog moves on to the next card', async () => {
  const { screen, state } = await startReview([FIRST, SECOND]);
  await expectCardShown(screen, FIRST);

  await userEvent.click(screen.getByRole('button', { name: 'Edit', exact: true }));
  const dialog = screen.getByRole('dialog', { name: 'Edit flashcard' });
  await userEvent.click(dialog.getByRole('button', { name: 'Delete' }));
  await userEvent.click(
    screen.getByRole('alertdialog').getByRole('button', { name: 'Delete', exact: true })
  );

  await expectCardShown(screen, SECOND);
  await expect.element(screen.getByText('2 of 2')).toBeVisible();
  await expect.poll(() => state.cards.map((card) => card.id)).toEqual([SECOND.id]);
  expect(state.reviews).toEqual([]);
});

test('grading the last card shows the done state', async () => {
  const { screen } = await startReview([FIRST]);
  await expectCardShown(screen, FIRST);

  await showAnswer(screen);
  await userEvent.click(gradeButton(screen, 'Good'));

  await expectAllCaughtUp(screen);
});

test('with nothing due the page shows the done state', async () => {
  const { screen } = await startReview([]);

  await expectAllCaughtUp(screen);
});

test('?book= reviews only that book', async () => {
  const otherBook = aDueFlashcard({ id: 801, book_id: 2, question: 'What is a map' });
  const { screen, state } = await startReview([otherBook, FIRST], '/review?book=1');
  await expectCardShown(screen, FIRST);
  await expect.element(screen.getByText('1 of 1')).toBeVisible();

  await showAnswer(screen);
  await userEvent.click(gradeButton(screen, 'Good'));

  await expectAllCaughtUp(screen);
  expect(state.dueListRequests.every((request) => request.bookId === 1)).toBe(true);
  await expect.poll(() => state.reviews.map((review) => review.flashcardId)).toEqual([FIRST.id]);
});

test('a queue longer than a page loads the rest before it runs out', async () => {
  const cards = cardsNumbered(53);
  const { screen, state } = await startReview(cards);
  await expect.element(screen.getByText('1 of 53')).toBeVisible();

  for (const card of cards) {
    await expectCardShown(screen, card);
    await userEvent.keyboard(' ');
    await userEvent.keyboard('3');
  }

  await expectAllCaughtUp(screen);
  await expect.poll(() => state.reviews).toHaveLength(53);
  expect(state.dueListRequests.length).toBeGreaterThan(1);
  expect(state.dueListRequests.every((request) => request.limit === 50)).toBe(true);
});

test('a page that fails to load near the end can be tried again', async () => {
  const cards = cardsNumbered(53);
  const { screen } = await startReview(cards);
  await expectCardShown(screen, cards[0]);
  let failing = true;
  worker.use(
    http.get('/api/v1/flashcards/due', () =>
      failing ? HttpResponse.json(null, { status: 500 }) : undefined
    )
  );

  for (const card of cards.slice(0, 50)) {
    await expectCardShown(screen, card);
    await userEvent.keyboard(' ');
    await userEvent.keyboard('3');
  }

  await expectAlertRaised(screen);
  expect(screen.getByRole('status').elements()).toHaveLength(0);

  failing = false;
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }));

  await expectCardShown(screen, cards[50]);
});

test('review is a destination in the app bar', async () => {
  const { screen } = await startReview([]);

  await expect
    .element(screen.getByRole('link', { name: 'Review', exact: true }))
    .toHaveAttribute('data-status', 'active');
});
