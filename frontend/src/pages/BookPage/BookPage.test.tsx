import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { aNote } from '@tests/fixtures/notes';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
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

test('a blurb that already fits shows no expand toggle', async () => {
  const { handlers } = bookApi({ book: aBookDetails({ description: 'Short and complete.' }) });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByText('Short and complete.')).toBeVisible();
  await expect(screen.getByRole('button', { name: 'Show more' }).query()).toBeNull();
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

test('a blurb can be written in the manage dialog and appears in the header', async () => {
  const { handlers, state } = bookApi({ book: aBookDetails({ description: null }) });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await screen.getByRole('button', { name: 'Manage book' }).click();
  await screen.getByRole('textbox', { name: 'Blurb' }).fill('A book about **attention**.');
  await screen.getByRole('button', { name: 'Save' }).click();

  // The dialog's own textarea contains the raw typed text while the save is
  // in flight, so 'attention' can substring-match it even before the header
  // re-renders. Wait for the dialog to close first, so the assertion below
  // is only provable once the header itself carries the saved blurb.
  await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();
  await expect.element(screen.getByText('attention')).toBeVisible();
  expect(state.book.description).toBe('A book about **attention**.');
});

test('a failed blurb save reports the error and keeps the typed edit and the original blurb', async () => {
  const { handlers } = bookApi({
    book: aBookDetails({ description: 'The original blurb.' }),
  });
  worker.use(...handlers);
  // Registered last, so it takes precedence over the happy-path PATCH above.
  worker.use(http.patch('/api/v1/books/:bookId', () => new HttpResponse(null, { status: 500 })));

  const screen = await renderApp({ path: '/book/1' });
  await expect.element(screen.getByText('The original blurb.')).toBeVisible();

  await screen.getByRole('button', { name: 'Manage book' }).click();
  await screen.getByRole('textbox', { name: 'Blurb' }).fill('A doomed edit about attention.');
  await screen.getByRole('button', { name: 'Save' }).click();

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Failed to save blurb' }))
    .toBeVisible();

  // The dialog stayed open with the reader's typed text still in the field...
  const dialog = screen.getByRole('dialog');
  await expect.element(dialog).toBeInTheDocument();
  await expect
    .element(dialog.getByRole('textbox', { name: 'Blurb' }))
    .toHaveValue('A doomed edit about attention.');

  // ...and closing without retrying leaves the original blurb on screen.
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect.element(screen.getByText('The original blurb.')).toBeVisible();

  // Reopening must not resurrect the abandoned draft: the field should show
  // the real blurb, not the text left over from the failed save.
  await screen.getByRole('button', { name: 'Manage book' }).click();
  await expect
    .element(screen.getByRole('textbox', { name: 'Blurb' }))
    .toHaveValue('The original blurb.');
});

test('shortening an expanded blurb collapses it again', async () => {
  const { handlers } = bookApi({
    book: aBookDetails({ description: 'A long sentence about attention. '.repeat(40) }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });
  await screen.getByRole('button', { name: 'Show more' }).click();
  await expect.element(screen.getByRole('button', { name: 'Show less' })).toBeVisible();

  await screen.getByRole('button', { name: 'Manage book' }).click();
  await screen.getByRole('textbox', { name: 'Blurb' }).fill('Short and complete.');
  await screen.getByRole('button', { name: 'Save' }).click();

  await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();
  await expect.element(screen.getByText('Short and complete.')).toBeVisible();
  await expect(screen.getByRole('button', { name: 'Show less' }).query()).toBeNull();
  await expect(screen.getByRole('button', { name: 'Show more' }).query()).toBeNull();
});

test('clearing the blurb removes it from the header', async () => {
  const { handlers, state } = bookApi({
    book: aBookDetails({ description: 'A blurb worth deleting.' }),
  });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1' });
  await expect.element(screen.getByText('A blurb worth deleting.')).toBeVisible();

  await screen.getByRole('button', { name: 'Manage book' }).click();
  await screen.getByRole('textbox', { name: 'Blurb' }).fill('');
  await screen.getByRole('button', { name: 'Save' }).click();

  await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();
  await expect.element(screen.getByText('A blurb worth deleting.')).not.toBeInTheDocument();
  expect(state.book.description).toBeNull();
});
