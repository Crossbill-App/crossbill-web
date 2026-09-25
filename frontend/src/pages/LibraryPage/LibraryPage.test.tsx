import type { Book } from '@/api/generated/model';
import { aBookCard, aBookDetails } from '@tests/fixtures/book';
import { fakeTheClock } from '@tests/harness/fakeClock';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { libraryApi } from '@tests/msw/libraryApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test, vi } from 'vitest';
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
  fakeTheClock();
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

  // A half-typed query stays in the box however long the reader pauses.
  await vi.advanceTimersByTimeAsync(60_000);
  expect(window.location.search).not.toContain('search=');
  await expect.element(screen.getByText('Every Book')).toBeVisible();

  await userEvent.keyboard('{Enter}');

  await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();
  expect(window.location.search).toContain('search=pragmatic');
});

const anEpub = (name = 'book.epub') =>
  new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], name, { type: 'application/epub+zip' });

// The picker is the browser's own dialog, so the file goes straight to the input it fills.
const chooseFile = async (file: File) => {
  await userEvent.upload(document.querySelector<HTMLInputElement>('input[type="file"]')!, file);
};

test('uploading an EPUB adds the book and opens it', async () => {
  const uploaded: string[] = [];
  worker.use(
    ...libraryApi([]),
    http.post('/api/v1/books/', async ({ request }) => {
      const epub = (await request.formData()).get('epub');
      uploaded.push(epub instanceof File ? epub.name : '');
      return HttpResponse.json(
        {
          id: 7,
          title: 'Uploaded Book',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        } satisfies Book,
        { status: 201 }
      );
    }),
    ...bookApi({ book: aBookDetails({ id: 7, title: 'Uploaded Book' }) }).handlers
  );

  const screen = await renderApp({ path: '/library' });
  await expect.element(screen.getByRole('status')).toBeVisible();

  await chooseFile(anEpub('dune.epub'));

  await expect.element(screen.getByRole('heading', { name: 'Uploaded Book' })).toBeVisible();
  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Uploaded Book' }))
    .toBeVisible();
  expect(window.location.pathname).toBe('/book/7/structure');
  expect(uploaded).toEqual(['dune.epub']);
});

test('an EPUB already in the library is refused and the library stays open', async () => {
  worker.use(
    ...libraryApi([]),
    http.post('/api/v1/books/', () =>
      HttpResponse.json({ error: 'Conflict', message: 'Book already exists' }, { status: 409 })
    )
  );

  const screen = await renderApp({ path: '/library' });
  await expect.element(screen.getByRole('status')).toBeVisible();

  await chooseFile(anEpub());

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'already in your library' }))
    .toBeVisible();
  expect(window.location.pathname).toBe('/library');
});

test('a file that is not an EPUB is refused without being sent', async () => {
  let posts = 0;
  worker.use(
    ...libraryApi([]),
    http.post('/api/v1/books/', () => {
      posts += 1;
      return new HttpResponse(null, { status: 201 });
    })
  );

  const screen = await renderApp({ path: '/library' });
  await expect.element(screen.getByRole('status')).toBeVisible();

  await chooseFile(new File(['plain text'], 'notes.txt', { type: 'text/plain' }));

  await expect.element(screen.getByRole('alert')).toBeVisible();
  expect(posts).toBe(0);
});
