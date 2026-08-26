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

const touchAt = (clientX: number, clientY: number) =>
  new Touch({ identifier: 1, target: document.body, clientX, clientY });

const dispatch = (type: string, touches: Touch[]) => {
  const event = new TouchEvent(type, { touches, cancelable: true, bubbles: true });
  window.dispatchEvent(event);
  return event;
};

/**
 * One complete drag from the top of the page, in steps small enough that the
 * gesture passes through the direction lock the way a real finger does.
 * Returns whether the page swallowed the movement.
 */
const drag = ({ x = 0, y = 0 }: { x?: number; y?: number }) => {
  const STEPS = 10;
  dispatch('touchstart', [touchAt(0, 0)]);

  let prevented = false;
  for (let step = 1; step <= STEPS; step += 1) {
    const move = dispatch('touchmove', [touchAt((x * step) / STEPS, (y * step) / STEPS)]);
    prevented ||= move.defaultPrevented;
  }

  dispatch('touchend', []);
  return { prevented };
};

/** One complete downward drag from the top of the page. */
const dragDown = (distance: number) => drag({ y: distance });

const ORIGINAL_TITLE = 'The Pragmatic Reader';
const REFRESHED_TITLE = 'The Refreshed Reader';

/**
 * The front page on screen showing the original title, with the API primed to
 * answer the next request with the refreshed one — so a refetch shows up as a
 * changed title rather than only as a request count.
 */
async function aFrontPageReadyToRefresh() {
  const { handlers, state } = booksApi(ORIGINAL_TITLE);
  worker.use(...handlers);

  const screen = await renderApp({ path: '/' });
  await expect.element(screen.getByText(ORIGINAL_TITLE)).toBeVisible();

  state.title = REFRESHED_TITLE;

  return { screen, state };
}

type FrontPage = Awaited<ReturnType<typeof aFrontPageReadyToRefresh>>;

/**
 * Nothing refetched: still the one request, still the original title. A
 * refresh fires its request off the touchend handler, so whatever the drag was
 * going to do has reached the handler well inside this window.
 */
async function expectNoRefresh({ screen, state }: FrontPage) {
  await new Promise((resolve) => setTimeout(resolve, 300));

  expect(state.requests).toBe(1);
  await expect.element(screen.getByText(ORIGINAL_TITLE)).toBeVisible();
}

test('pulling the page down past the threshold refetches the data on screen', async () => {
  const { screen } = await aFrontPageReadyToRefresh();

  dragDown(300);

  await expect.element(screen.getByText(REFRESHED_TITLE)).toBeVisible();
});

test('a pull that stops short of the threshold refetches nothing', async () => {
  const page = await aFrontPageReadyToRefresh();

  // 30px of pull once resistance is applied: under the 70px threshold.
  dragDown(60);

  await expectNoRefresh(page);
});

test('a sideways swipe is left to the horizontal scroller under it', async () => {
  const page = await aFrontPageReadyToRefresh();

  // A carousel drag: far enough sideways to be horizontal, with the vertical
  // drift a finger leaves behind — and past the refresh threshold on its own.
  const { prevented } = drag({ x: -240, y: 200 });

  expect(prevented).toBe(false);
  await expectNoRefresh(page);
});
