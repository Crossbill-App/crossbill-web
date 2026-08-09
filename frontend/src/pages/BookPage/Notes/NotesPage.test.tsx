import { aBookDetails } from '@tests/fixtures/book';
import { aNote } from '@tests/fixtures/notes';
import { aNoteHit } from '@tests/fixtures/semantic';
import { renderApp } from '@tests/harness/renderApp';
import { settingsWithEmbeddings } from '@tests/msw/auth';
import { bookApi } from '@tests/msw/bookApi';
import { semanticSearchApi } from '@tests/msw/semanticSearchApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

const NOTES_SEARCH_PLACEHOLDER = 'Search notes by meaning…';

const openNoteForEditing = async (screen: Screen, title: string) => {
  await userEvent.click(screen.getByRole('button', { name: new RegExp(title) }));
  await userEvent.click(screen.getByRole('button', { name: 'Edit note' }));
};

/**
 * Two notes on the page — enough for a search to prove it intersects with
 * the page's own list rather than rendering hits verbatim. Author overridden:
 * the default 'Ada Lovelace' collides with a note of the same title, and the
 * book title heading persists through filtering.
 */
const aTwoNoteBook = () =>
  bookApi({
    book: aBookDetails({ author: 'Grace Hopper' }),
    notes: [
      aNote({ id: 100, title: 'Ada Lovelace' }),
      aNote({ id: 101, title: 'Difference Engine' }),
    ],
  });

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

test('searching notes lists only the notes on this page that matched', async () => {
  const { handlers } = aTwoNoteBook();
  worker.use(
    settingsWithEmbeddings(true),
    ...semanticSearchApi({
      engines: {
        notes: [
          aNoteHit({ id: 101, title: 'Difference Engine', score: 0.71 }),
          // A hit the page does not hold: notes can link to several books, so
          // the page must intersect with its own list, not render hits.
          aNoteHit({ id: 999, title: 'Analytical Engine', score: 0.9 }),
        ],
      },
    }),
    ...handlers
  );

  const screen = await renderApp({ path: '/book/1/notes' });
  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();

  await userEvent.fill(screen.getByPlaceholder(NOTES_SEARCH_PLACEHOLDER), 'engines');
  await userEvent.keyboard('{Enter}');

  await expect
    .element(screen.getByRole('heading', { name: 'Ada Lovelace' }))
    .not.toBeInTheDocument();
  await expect.element(screen.getByRole('heading', { name: 'Difference Engine' })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Analytical Engine' }).elements()).toHaveLength(0);
});

test('a query that matches none of the notes on this page shows the search empty state', async () => {
  const { handlers } = aTwoNoteBook();
  worker.use(
    settingsWithEmbeddings(true),
    // Unlisted query → every group comes back empty, i.e. nothing matched.
    ...semanticSearchApi({ underwater: {} }),
    ...handlers
  );

  const screen = await renderApp({ path: '/book/1/notes' });
  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();

  await userEvent.fill(screen.getByPlaceholder(NOTES_SEARCH_PLACEHOLDER), 'underwater');
  await userEvent.keyboard('{Enter}');

  await expect.element(screen.getByText(/No notes match/)).toBeVisible();
  await expect
    .element(screen.getByRole('heading', { name: 'Ada Lovelace' }))
    .not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Difference Engine' }).elements()).toHaveLength(0);
});

test('a failed search reports the error and keeps every note listed', async () => {
  const { handlers } = bookApi({
    // Same author override as above, and for the same reason.
    book: aBookDetails({ author: 'Grace Hopper' }),
    notes: [aNote({ id: 100, title: 'Ada Lovelace' })],
  });
  worker.use(
    settingsWithEmbeddings(true),
    http.get('/api/v1/semantic/search', () => new HttpResponse(null, { status: 500 })),
    ...handlers
  );

  const screen = await renderApp({ path: '/book/1/notes' });
  await userEvent.fill(screen.getByPlaceholder(NOTES_SEARCH_PLACEHOLDER), 'engines');
  await userEvent.keyboard('{Enter}');

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Search failed' }))
    .toBeVisible();
  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();
});
