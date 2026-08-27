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

test('a blurb renders as markdown and starts collapsed', async () => {
  const { handlers } = bookApi({
    book: aBookDetails({
      description: '**Winner** of nothing.\n\n' + 'A long sentence about attention. '.repeat(40),
    }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByText('Winner')).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Show more' })).toBeVisible();

  await screen.getByRole('button', { name: 'Show more' }).click();

  await expect.element(screen.getByRole('button', { name: 'Show less' })).toBeVisible();
});

test('a book with no blurb shows no blurb controls', async () => {
  const { handlers } = bookApi({ book: aBookDetails({ description: null }) });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();
  await expect(screen.getByRole('button', { name: 'Show more' }).query()).toBeNull();
});

test('html in a publisher blurb renders as markup, not as visible tags', async () => {
  const { handlers } = bookApi({
    book: aBookDetails({ description: '<p>From the <em>publisher</em>.</p>' }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByText('publisher')).toBeVisible();
  await expect(screen.getByText('<p>', { exact: false }).query()).toBeNull();
});

test('a dangerous payload in a blurb is stripped by the sanitiser, not just hidden by rehypeRaw', async () => {
  const { handlers } = bookApi({
    book: aBookDetails({
      description: 'Safe blurb.\n\n<img src="x" onerror="alert(1)"><script>alert(1)</script>',
    }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByText('Safe blurb.')).toBeVisible();
  expect(screen.container.querySelector('script')).toBeNull();
  expect(screen.container.querySelector('img[onerror]')).toBeNull();
});
