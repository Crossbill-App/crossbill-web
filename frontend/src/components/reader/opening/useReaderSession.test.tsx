import {
  useReaderSession,
  type ReaderSession,
} from '@/components/reader/opening/useReaderSession.ts';
import { fakeTheClock } from '@tests/harness/fakeClock';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { useEffect } from 'react';
import { beforeEach, expect, test, vi } from 'vitest';
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

/** The lifetime the server gives a cookie. */
const COOKIE_LIFE_S = 900;

/** The date jumps with no timer run, as on a machine that slept through the cookie. */
const sleepThroughTheCookie = () => vi.setSystemTime(Date.now() + COOKIE_LIFE_S * 1000);

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

/** A mint the last session wrongly sent would reach the server before this one's and be counted. */
const expectTheNextSessionToMintAfter = async (earlier: string[]) => {
  const screen = await render(<Probe />);
  await expectStatus(screen, 'ready');
  expect(posts).toEqual([...earlier, 'minted']);
};

test('a session is ready once the first cookie has been minted', async () => {
  worker.use(aSessionLasting(COOKIE_LIFE_S));

  const screen = await render(<Probe />);

  await expectStatus(screen, 'ready');
  expect(renewals).toEqual([false]);
  expect(posts).toEqual(['minted']);
});

test('a session the server refuses before any cookie exists is fatal', async () => {
  fakeTheClock();
  worker.use(aSessionLasting(COOKIE_LIFE_S));
  worker.use(aRefusedSession(500, { once: true }));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'error');

  // Past every retry delay, so a retry the failure wrongly scheduled has been sent.
  await vi.advanceTimersByTimeAsync(60_000);
  await screen.unmount();

  await expectTheNextSessionToMintAfter(['refused']);
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
  fakeTheClock();
  worker.use(aSessionLasting(COOKIE_LIFE_S));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'ready');

  sleepThroughTheCookie();
  worker.use(aRefusedSession(500, { once: true }));
  window.dispatchEvent(new Event('focus'));

  await expect.element(screen.getByTestId('renewing')).toHaveTextContent('true');
  await expect.poll(() => posts).toEqual(['minted', 'refused']);
  await expectStatus(screen, 'ready');

  await vi.advanceTimersByTimeAsync(1_000);

  await expect.element(screen.getByTestId('renewing')).toHaveTextContent('false');
  expect(posts).toEqual(['minted', 'refused', 'minted']);
});

test('renewing before the cookie lapses is invisible', async () => {
  fakeTheClock();
  worker.use(aSessionLasting(COOKIE_LIFE_S));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'ready');

  // Inside the 30 s wake margin, with the cookie still good.
  vi.setSystemTime(Date.now() + (COOKIE_LIFE_S - 20) * 1000);
  window.dispatchEvent(new Event('focus'));

  await expect.poll(() => posts).toEqual(['minted', 'minted']);
  expect(renewals).toEqual([false]);
});

test('an unmounted session mints nothing more', async () => {
  fakeTheClock();
  worker.use(aSessionLasting(COOKIE_LIFE_S));

  const screen = await render(<Probe />);
  await expectStatus(screen, 'ready');
  await screen.unmount();

  // Past the scheduled renewal and the cookie, so a session still mounted would
  // renew both on its timer and on this focus.
  await vi.advanceTimersByTimeAsync(COOKIE_LIFE_S * 1000);
  window.dispatchEvent(new Event('focus'));

  await expectTheNextSessionToMintAfter(['minted']);
});
