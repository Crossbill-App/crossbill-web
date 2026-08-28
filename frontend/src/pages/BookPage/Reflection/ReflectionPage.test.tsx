import { aBookDetails } from '@tests/fixtures/book';
import { aNote } from '@tests/fixtures/notes';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const ANSWER_NOTE_ID = 100;

const renderReflection = async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    notes: [
      aNote({
        id: ANSWER_NOTE_ID,
        title: 'What is the book about?',
        body: 'A book about reading well.',
        kind: 'reflection',
      }),
      aNote({ id: 101, title: 'Attention', kind: 'concept' }),
    ],
  });
  worker.use(
    ...handlers,
    http.get('/api/v1/books/:bookId/reflection', () =>
      HttpResponse.json({ book_id: 1, what_is_it_about_note_id: ANSWER_NOTE_ID, note_ids: [] })
    )
  );

  return renderApp({ path: '/book/1/reflection' });
};

test('editing a reflection answer opens the note dialog already in edit mode', async () => {
  const screen = await renderReflection();
  await expect.element(screen.getByText('A book about reading well.')).toBeVisible();

  await userEvent.click(screen.getByRole('button', { name: 'Edit answer' }));

  const dialog = screen.getByRole('dialog');
  // The editor itself, not a read view with an Edit button.
  await expect.element(dialog.getByRole('textbox', { name: 'Title' })).toBeVisible();
  // The reflection question stays on screen beside the form.
  await expect.element(dialog.getByText('What is the book about?')).toBeVisible();

  await userEvent.fill(
    dialog.getByRole('textbox', { name: 'Note (markdown)' }),
    'A book about reading better.'
  );
  await userEvent.click(dialog.getByRole('button', { name: 'Save' }));
  await userEvent.click(dialog.getByRole('button', { name: 'Close dialog' }));

  await expect.element(screen.getByText('A book about reading better.')).toBeVisible();
});

test('cancelling the edit falls back to the note, not out of the dialog', async () => {
  const screen = await renderReflection();

  await userEvent.click(screen.getByRole('button', { name: 'Edit answer' }));
  const dialog = screen.getByRole('dialog');
  await userEvent.click(dialog.getByRole('button', { name: 'Cancel' }));

  await expect.element(dialog.getByRole('button', { name: 'Edit note' })).toBeVisible();
});

test("the note picker names a note's type the way the cards do", async () => {
  const screen = await renderReflection();

  await userEvent.click(screen.getByRole('button', { name: 'Link existing note' }));

  const picker = screen.getByRole('dialog');
  await expect.element(picker.getByText('Attention')).toBeVisible();
  // The API sends "concept"; the reader is shown the label, as on every card.
  await expect.element(picker.getByText('Concept')).toBeVisible();
  expect(picker.getByText('concept', { exact: true }).elements()).toHaveLength(0);
});
