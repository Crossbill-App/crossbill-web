import { aBookCard } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { libraryApi } from '@tests/msw/libraryApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

test('a book card shows what the reader has made of the book', async () => {
  worker.use(
    ...libraryApi([
      aBookCard({
        title: 'The Pragmatic Reader',
        highlight_count: 412,
        note_count: 6,
        flashcard_count: 38,
      }),
    ])
  );

  const screen = await renderApp({ path: '/library' });

  await expect.element(screen.getByRole('img', { name: '412 highlights' })).toBeVisible();
  await expect.element(screen.getByRole('img', { name: '6 notes' })).toBeVisible();
  await expect.element(screen.getByRole('img', { name: '38 flashcards' })).toBeVisible();
});

test('a count the book has none of is left off the card', async () => {
  worker.use(
    ...libraryApi([
      aBookCard({ title: 'Untouched', highlight_count: 3, note_count: 0, flashcard_count: 0 }),
    ])
  );

  const screen = await renderApp({ path: '/library' });

  await expect.element(screen.getByRole('img', { name: '3 highlights' })).toBeVisible();
  expect(screen.getByRole('img', { name: /notes?$/ }).query()).toBeNull();
  expect(screen.getByRole('img', { name: /flashcards?$/ }).query()).toBeNull();
});

test('a single count reads in the singular', async () => {
  worker.use(...libraryApi([aBookCard({ highlight_count: 1, note_count: 1 })]));

  const screen = await renderApp({ path: '/library' });

  await expect.element(screen.getByRole('img', { name: '1 highlight' })).toBeVisible();
  await expect.element(screen.getByRole('img', { name: '1 note' })).toBeVisible();
});

test('a book nobody has marked up carries no strip', async () => {
  worker.use(
    ...libraryApi([
      aBookCard({ title: 'Untouched', highlight_count: 0, note_count: 0, flashcard_count: 0 }),
    ])
  );

  const screen = await renderApp({ path: '/library' });

  await expect.element(screen.getByText('Untouched')).toBeVisible();
  expect(screen.getByTestId('book-counts').query()).toBeNull();
});

test('a link to the old all-books page still finds the books it searched for', async () => {
  worker.use(...libraryApi([aBookCard({ title: 'The Pragmatic Reader' })]));

  const screen = await renderApp({ path: '/?search=pragmatic&page=1' });

  await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();
  expect(window.location.pathname).toBe('/library');
  expect(window.location.search).toContain('search=pragmatic');
});

test('the search runs on Enter, not while the query is still being typed', async () => {
  worker.use(
    http.get('/api/v1/books/', ({ request }) => {
      const query = new URL(request.url).searchParams.get('search');
      const books = [aBookCard({ title: query ? 'The Pragmatic Reader' : 'Every Book' })];
      return HttpResponse.json({ items: books, total: books.length, offset: 0, limit: 32 });
    }),
    ...libraryApi([])
  );

  const screen = await renderApp({ path: '/library' });
  await expect.element(screen.getByText('Every Book')).toBeVisible();

  await userEvent.fill(screen.getByPlaceholder('Search books by title or author...'), 'pragmatic');

  // Longer than the debounce this field used to carry: a half-typed query now
  // stays in the box however long the reader pauses.
  await new Promise((resolve) => setTimeout(resolve, 500));
  expect(window.location.search).not.toContain('search=');
  await expect.element(screen.getByText('Every Book')).toBeVisible();

  await userEvent.keyboard('{Enter}');

  await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();
  expect(window.location.search).toContain('search=pragmatic');
});
