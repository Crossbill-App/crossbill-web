import { useReaderSession, type ReaderSession } from '@/components/reader/useReaderSession.ts';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { useEffect } from 'react';
import { beforeEach, expect, test } from 'vitest';
import { render } from 'vitest-browser-react';

const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const REFRESH_PATH = '/api/v1/auth/refresh';

const posts: string[] = [];
const renewals: boolean[] = [];

beforeEach(() => {
  posts.length = 0;
  renewals.length = 0;
});

const aSessionLasting = (seconds: number) =>
  http.post(SESSION_PATH, () => {
    posts.push('minted');
    return HttpResponse.json({ expires_in: seconds });
  });

const aRefusedSession = (status: number, options?: { once: boolean }) =>
  http.post(
    SESSION_PATH,
    () => {
      posts.push('refused');
      return new HttpResponse(null, { status });
    },
    options
  );

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const Probe = () => {
  const { status, isRenewing } = useReaderSession(1);

  useEffect(() => {
    if (renewals[renewals.length - 1] !== isRenewing) renewals.push(isRenewing);
  }, [isRenewing]);

  return (
    <>
      <output data-testid="status">{status}</output>
      <output data-testid="renewing">{String(isRenewing)}</output>
    </>
  );
};

type Screen = Awaited<ReturnType<typeof render>>;

const expectStatus = (screen: Screen, status: ReaderSession['status']) =>
  expect.element(screen.getByTestId('status')).toHaveTextContent(status);

test('a session is ready once the first cookie has been minted', async () => {
  worker.use(aSessionLasting(900));

  const screen = await render(<Probe />);

  await expectStatus(screen, 'ready');
  expect(renewals).toEqual([false]);
  expect(posts).toEqual(['minted']);
});

test('a session the server refuses before any cookie exists is fatal', async () => {
  worker.use(aRefusedSession(500));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'error');

  // Past the shortest retry delay (1 s): a first failure must schedule none.
  await sleep(1_500);

  await expectStatus(screen, 'error');
  expect(posts).toEqual(['refused']);
});

test('a 401 the app cannot refresh past is fatal too', async () => {
  // A refresh the server rejects ends the session app-wide, and the axios layer
  // says so by navigating to /login — which would unload the test page. On that
  // path the redirect is a no-op, leaving only the rejection the hook sees.
  window.history.pushState(null, '', '/login');
  worker.use(aRefusedSession(401));
  worker.use(http.post(REFRESH_PATH, () => new HttpResponse(null, { status: 401 })));

  const screen = await render(<Probe />);

  await expectStatus(screen, 'error');
});

test('a failed renewal keeps the session and retries', async () => {
  worker.use(aSessionLasting(1));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'ready');

  // Past the 1 s cookie but under the 5 s refresh floor, so nothing has renewed it.
  await sleep(1_200);
  worker.use(aSessionLasting(900));
  worker.use(aRefusedSession(500, { once: true }));
  window.dispatchEvent(new Event('focus'));

  await expect.element(screen.getByTestId('renewing')).toHaveTextContent('true');
  await expectStatus(screen, 'ready');

  // The first retry lands a second later.
  await expect
    .element(screen.getByTestId('renewing'), { timeout: 2_000 })
    .toHaveTextContent('false');
  expect(posts).toEqual(['minted', 'refused', 'minted']);
});

test('renewing before the cookie lapses is invisible', async () => {
  worker.use(aSessionLasting(5));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'ready');

  // A 5 s cookie is well inside the 30 s wake margin and nowhere near lapsing.
  await sleep(300);
  window.dispatchEvent(new Event('focus'));

  await expect.poll(() => posts).toEqual(['minted', 'minted']);
  expect(renewals).toEqual([false]);
});

test('an unmounted session mints nothing more', async () => {
  worker.use(aSessionLasting(1));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'ready');
  screen.unmount();

  // Past the 1 s cookie, so a session still mounted would renew on this focus.
  await sleep(1_200);
  window.dispatchEvent(new Event('focus'));
  await sleep(100);

  expect(posts).toEqual(['minted']);
});
