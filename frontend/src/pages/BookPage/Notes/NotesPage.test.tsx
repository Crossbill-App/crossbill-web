import { aBookDetails } from '@tests/fixtures/book';
import { aNote } from '@tests/fixtures/notes';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

const openNoteForEditing = async (screen: Screen, title: string) => {
  await userEvent.click(screen.getByRole('button', { name: new RegExp(title) }));
  await userEvent.click(screen.getByRole('button', { name: 'Edit note' }));
};

test('renaming a note updates the notes list', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    notes: [aNote({ id: 100, title: 'Analytical Engine' })],
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/notes' });
  await expect.element(screen.getByRole('heading', { name: 'Analytical Engine' })).toBeVisible();

  await openNoteForEditing(screen, 'Analytical Engine');
  const dialog = screen.getByRole('dialog');
  await userEvent.fill(dialog.getByRole('textbox', { name: 'Title' }), 'Difference Engine');
  await userEvent.click(dialog.getByRole('button', { name: 'Save' }));
  await userEvent.click(dialog.getByRole('button', { name: 'Close', exact: true }));

  await expect.element(screen.getByRole('heading', { name: 'Difference Engine' })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Analytical Engine' }).elements()).toHaveLength(0);
});

test('a failed save reports the error and leaves the note unchanged', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    notes: [aNote({ id: 100, title: 'Analytical Engine' })],
  });
  worker.use(...handlers);
  // Registered last, so it takes precedence over the happy-path PUT above.
  worker.use(http.put('/api/v1/notes/:noteId', () => new HttpResponse(null, { status: 500 })));

  const screen = await renderApp({ path: '/book/1/notes' });
  await expect.element(screen.getByRole('heading', { name: 'Analytical Engine' })).toBeVisible();

  await openNoteForEditing(screen, 'Analytical Engine');
  const dialog = screen.getByRole('dialog');
  await userEvent.fill(dialog.getByRole('textbox', { name: 'Title' }), 'Difference Engine');
  await userEvent.click(dialog.getByRole('button', { name: 'Save' }));

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Failed to update note' }))
    .toBeVisible();

  await userEvent.click(dialog.getByRole('button', { name: 'Cancel' }));
  await userEvent.click(dialog.getByRole('button', { name: 'Close', exact: true }));

  await expect.element(screen.getByRole('heading', { name: 'Analytical Engine' })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Difference Engine' }).elements()).toHaveLength(0);
});
