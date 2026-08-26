import { aBookDetails, aChapter } from '@tests/fixtures/book';
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
