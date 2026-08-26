import type { BookWithHighlightCount } from '@/api/generated/model';
import { renderApp } from '@tests/harness/renderApp';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';

const aBookListItem = (title: string): BookWithHighlightCount => ({
  id: 1,
  title,
  author: 'Ada Lovelace',
  isbn: null,
  cover_file: null,
  cover_blurhash: null,
  highlight_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
});

/**
 * The books list, whose single title can be changed between requests, so a
 * refetch is visible on screen rather than only in a request count.
 */
function booksApi(title: string) {
  const state = { title, requests: 0 };

  const handlers = [
    http.get('/api/v1/books/', () => {
      state.requests += 1;
      return HttpResponse.json({
        items: [aBookListItem(state.title)],
        total: 1,
        offset: 0,
        limit: 32,
      });
    }),
    http.get('/api/v1/books/recently-viewed', () => HttpResponse.json({ items: [] })),
  ];

  return { handlers, state };
}

const touchAt = (clientY: number) =>
  new Touch({ identifier: 1, target: document.body, clientX: 0, clientY });

/** One complete downward drag from the top of the page. */
const dragDown = (distance: number) => {
  const dispatch = (type: string, touches: Touch[]) =>
    window.dispatchEvent(new TouchEvent(type, { touches, cancelable: true, bubbles: true }));

  dispatch('touchstart', [touchAt(0)]);
  dispatch('touchmove', [touchAt(distance)]);
  dispatch('touchend', []);
};

test('pulling the page down past the threshold refetches the data on screen', async () => {
  const { handlers, state } = booksApi('The Pragmatic Reader');
  worker.use(...handlers);

  const screen = await renderApp({ path: '/' });
  await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();

  state.title = 'The Refreshed Reader';
  dragDown(300);

  await expect.element(screen.getByText('The Refreshed Reader')).toBeVisible();
});

test('a pull that stops short of the threshold refetches nothing', async () => {
  const { handlers, state } = booksApi('The Pragmatic Reader');
  worker.use(...handlers);

  const screen = await renderApp({ path: '/' });
  await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();

  state.title = 'The Refreshed Reader';
  // 30px of pull once resistance is applied: under the 70px threshold.
  dragDown(60);

  // A refresh fires its request off the touchend handler, so whatever this
  // drag was going to do has reached the handler well inside this window.
  await new Promise((resolve) => setTimeout(resolve, 300));

  expect(state.requests).toBe(1);
  await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();
});
