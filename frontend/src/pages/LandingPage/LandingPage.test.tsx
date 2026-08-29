import { aBookCard } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { libraryApi } from '@tests/msw/libraryApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';

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

  const screen = await renderApp({ path: '/' });

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

  const screen = await renderApp({ path: '/' });

  await expect.element(screen.getByRole('img', { name: '3 highlights' })).toBeVisible();
  expect(screen.getByRole('img', { name: /notes?$/ }).query()).toBeNull();
  expect(screen.getByRole('img', { name: /flashcards?$/ }).query()).toBeNull();
});

test('a single count reads in the singular', async () => {
  worker.use(...libraryApi([aBookCard({ highlight_count: 1, note_count: 1 })]));

  const screen = await renderApp({ path: '/' });

  await expect.element(screen.getByRole('img', { name: '1 highlight' })).toBeVisible();
  await expect.element(screen.getByRole('img', { name: '1 note' })).toBeVisible();
});

test('a book nobody has marked up carries no strip', async () => {
  worker.use(
    ...libraryApi([
      aBookCard({ title: 'Untouched', highlight_count: 0, note_count: 0, flashcard_count: 0 }),
    ])
  );

  const screen = await renderApp({ path: '/' });

  await expect.element(screen.getByText('Untouched')).toBeVisible();
  expect(screen.getByTestId('book-counts').query()).toBeNull();
});
