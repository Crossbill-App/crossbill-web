import { aBookDetails, aChapter, aFlashcard } from '@tests/fixtures/book';
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

  const dialog = screen.getByRole('dialog', { name: 'New flashcard' });
  await userEvent.fill(dialog.getByRole('textbox', { name: 'Question' }), 'What is a map?');
  await userEvent.fill(dialog.getByRole('textbox', { name: 'Answer' }), 'Not the territory.');
  await userEvent.click(dialog.getByRole('button', { name: 'Save' }));

  await expect
    .element(
      screen
        .getByRole('list', { name: 'Flashcards not in a chapter' })
        .getByRole('button', { name: 'What is a map?' })
    )
    .toBeVisible();
  await expect.element(dialog).not.toBeInTheDocument();
});

test('editing a flashcard updates the list', async () => {
  worker.use(...bookApi({ book: aBookWithAChapterCard() }).handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  const dialog = await openForEditing(screen);
  await expect.element(dialog.getByRole('textbox', { name: 'Answer' })).toHaveValue('A filter.');

  await userEvent.fill(
    dialog.getByRole('textbox', { name: 'Question' }),
    'What does attention do?'
  );
  await userEvent.click(dialog.getByRole('button', { name: 'Save' }));

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
});

test('deleting a flashcard from its dialog removes it from the list', async () => {
  worker.use(...bookApi({ book: aBookWithAChapterCard() }).handlers);

  const screen = await renderApp({ path: '/book/1/flashcards' });
  const dialog = await openForEditing(screen);
  await userEvent.click(dialog.getByRole('button', { name: 'Delete', exact: true }));
  await userEvent.click(
    screen.getByRole('alertdialog').getByRole('button', { name: 'Delete', exact: true })
  );

  await expect.element(dialog).not.toBeInTheDocument();
  await expect.element(screen.getByRole('main').getByRole('status')).toBeVisible();
  expect(screen.getByRole('button', { name: 'What is attention?' }).elements()).toHaveLength(0);
});
