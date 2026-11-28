import { aBookDetails, aChapter, aFlashcard } from '@tests/fixtures/book';
import { deleteFromFlashcardDialog, saveFlashcardDialog } from '@tests/harness/flashcardDialog';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

const aBookWithAChapterCard = () =>
  aBookDetails({
    chapters: [aChapter({ id: 10, name: 'On Attention' })],
    book_flashcards: [
      aFlashcard({ id: 700, chapter_id: 10, question: 'What is attention?', answer: 'A filter.' }),
    ],
  });

const chapterCards = (screen: Screen) =>
  screen.getByRole('list', { name: 'Flashcards in On Attention' });

const openForEditing = async (screen: Screen) => {
  await expect
    .element(chapterCards(screen).getByRole('button', { name: 'What is attention?' }))
    .toBeVisible();
  await userEvent.click(chapterCards(screen).getByRole('button', { name: 'Edit flashcard' }));
  return screen.getByRole('dialog', { name: 'Edit flashcard' });
};

test('a flashcard made on the flashcards page is filed under not in a chapter', async () => {
  worker.use(...bookApi({ book: aBookWithAChapterCard() }).handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  await userEvent.click(screen.getByRole('button', { name: 'New flashcard' }));

  await saveFlashcardDialog(screen, 'New flashcard', {
    question: 'What is a map?',
    answer: 'Not the territory.',
  });

  await expect
    .element(
      screen
        .getByRole('list', { name: 'Flashcards not in a chapter' })
        .getByRole('button', { name: 'What is a map?' })
    )
    .toBeVisible();
});

test('editing a flashcard updates the list', async () => {
  worker.use(...bookApi({ book: aBookWithAChapterCard() }).handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  const dialog = await openForEditing(screen);
  await expect.element(dialog.getByRole('textbox', { name: 'Answer' })).toHaveValue('A filter.');

  await saveFlashcardDialog(screen, 'Edit flashcard', { question: 'What does attention do?' });

  await expect
    .element(chapterCards(screen).getByRole('button', { name: 'What does attention do?' }))
    .toBeVisible();
  expect(
    chapterCards(screen).getByRole('button', { name: 'What is attention?' }).elements()
  ).toHaveLength(0);
});

test('a failed save reports the error and keeps what was typed', async () => {
  worker.use(
    http.put('/api/v1/flashcards/:flashcardId', () => new HttpResponse(null, { status: 500 })),
    ...bookApi({ book: aBookWithAChapterCard() }).handlers
  );

  const screen = await renderApp({ path: '/book/1/flashcards' });
  const dialog = await openForEditing(screen);
  await userEvent.fill(
    dialog.getByRole('textbox', { name: 'Question' }),
    'What does attention do?'
  );
  await userEvent.click(dialog.getByRole('button', { name: 'Save' }));

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Failed to update flashcard' }))
    .toBeVisible();
  await expect
    .element(dialog.getByRole('textbox', { name: 'Question' }))
    .toHaveValue('What does attention do?');

  await userEvent.click(dialog.getByRole('button', { name: 'Cancel' }));
  await expect
    .element(chapterCards(screen).getByRole('button', { name: 'What is attention?' }))
    .toBeVisible();
});

test('deleting a flashcard from its dialog removes it from the list', async () => {
  worker.use(...bookApi({ book: aBookWithAChapterCard() }).handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  await openForEditing(screen);
  await deleteFromFlashcardDialog(screen);

  await expect.element(screen.getByRole('main').getByRole('status')).toBeVisible();
  expect(screen.getByRole('button', { name: 'What is attention?' }).elements()).toHaveLength(0);
});

const aBookWithASuspendedCard = () =>
  aBookDetails({
    chapters: [aChapter({ id: 10, name: 'On Attention' })],
    book_flashcards: [
      aFlashcard({ id: 700, chapter_id: 10, question: 'What is attention?' }),
      aFlashcard({ id: 701, chapter_id: 10, question: 'What is memory?', status: 'suspended' }),
    ],
  });

const cardFor = (screen: Screen, question: string) =>
  chapterCards(screen).getByRole('listitem').filter({ hasText: question });

const expectSuspended = async (screen: Screen, question: string) => {
  const card = cardFor(screen, question);
  await expect.element(card.getByText('Suspended', { exact: true })).toBeVisible();
  await expect.element(card.getByRole('button', { name: 'Unsuspend flashcard' })).toBeVisible();
};

const expectActive = async (screen: Screen, question: string) => {
  const card = cardFor(screen, question);
  await expect.element(card.getByRole('button', { name: question })).toBeVisible();
  await expect.element(card.getByText('Suspended', { exact: true })).not.toBeInTheDocument();
  await expect
    .element(card.getByRole('button', { name: 'Unsuspend flashcard' }))
    .not.toBeInTheDocument();
};

test('only a suspended flashcard is labelled suspended and offers unsuspend', async () => {
  worker.use(...bookApi({ book: aBookWithASuspendedCard() }).handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });

  await expectSuspended(screen, 'What is memory?');
  await expectActive(screen, 'What is attention?');
});

test('unsuspending a flashcard puts it back in review', async () => {
  const api = bookApi({ book: aBookWithASuspendedCard() });
  worker.use(...api.handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  await userEvent.click(
    cardFor(screen, 'What is memory?').getByRole('button', { name: 'Unsuspend flashcard' })
  );

  await expectActive(screen, 'What is memory?');
  expect(api.state.book.book_flashcards?.map((card) => card.status)).toEqual(['active', 'active']);
});

test('a failed unsuspend reports the error and leaves the card suspended', async () => {
  worker.use(
    http.put(
      '/api/v1/flashcards/:flashcardId/status',
      () => new HttpResponse(null, { status: 500 })
    ),
    ...bookApi({ book: aBookWithASuspendedCard() }).handlers
  );

  const screen = await renderApp({ path: '/book/1/flashcards' });
  await userEvent.click(
    cardFor(screen, 'What is memory?').getByRole('button', { name: 'Unsuspend flashcard' })
  );

  await expect.element(screen.getByRole('alert')).toBeVisible();
  await expectSuspended(screen, 'What is memory?');
});

test('editing a suspended flashcard leaves it suspended', async () => {
  const api = bookApi({ book: aBookWithASuspendedCard() });
  worker.use(...api.handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  await userEvent.click(
    cardFor(screen, 'What is memory?').getByRole('button', { name: 'Edit flashcard' })
  );
  await saveFlashcardDialog(screen, 'Edit flashcard', { question: 'What does memory keep?' });

  await expect
    .element(chapterCards(screen).getByRole('button', { name: 'What does memory keep?' }))
    .toBeVisible();
  await expectSuspended(screen, 'What does memory keep?');
  expect(api.state.book.book_flashcards?.[1].status).toBe('suspended');
});
