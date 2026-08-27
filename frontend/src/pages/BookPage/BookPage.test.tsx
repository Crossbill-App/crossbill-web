import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { aNote } from '@tests/fixtures/notes';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';

test('renders the book and its chapters', async () => {
  const { handlers } = bookApi({
    book: aBookDetails({
      title: 'The Pragmatic Reader',
      author: 'Ada Lovelace',
      chapters: [aChapter({ id: 10, name: 'On Attention' })],
    }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();
  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();
  await expect.element(screen.getByText('On Attention')).toBeVisible();
});

test('a book can be marked as not finished, and the chip keeps saying so', async () => {
  const { handlers, state } = bookApi({
    book: aBookDetails({ reading_stage: 'reading' }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await screen.getByRole('button', { name: 'Reading' }).click();
  await screen.getByRole('menuitem', { name: 'Did not finish' }).click();

  await expect.element(screen.getByRole('button', { name: 'Did not finish' })).toBeVisible();
  expect(state.book.reading_stage).toBe('did_not_finish');
});

test('the stats strip counts highlights, notes, flashcards and reading sessions', async () => {
  const { handlers } = bookApi({
    book: aBookDetails({
      chapters: [aChapter({ highlights: [aHighlight({ id: 300 }), aHighlight({ id: 301 })] })],
    }),
    notes: [aNote({ id: 1 }), aNote({ id: 2, kind: null })],
    sessionTotal: 8,
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByText('2 highlights')).toBeVisible();
  await expect.element(screen.getByText('2 notes')).toBeVisible();
  await expect.element(screen.getByText('0 flashcards')).toBeVisible();
  await expect.element(screen.getByText('8 sessions')).toBeVisible();
});

// Gists are auto-generated per chapter and the Notes tab hides them by
// default, so counting them here would show a total the tab never matches.
test('the note count leaves out gists', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    notes: [aNote({ id: 1 }), aNote({ id: 2, kind: 'gist' }), aNote({ id: 3, kind: 'gist' })],
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByText('1 notes')).toBeVisible();
});
