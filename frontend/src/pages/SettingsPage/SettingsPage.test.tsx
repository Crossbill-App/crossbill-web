import { aJobBatch } from '@tests/fixtures/jobs';
import { renderApp } from '@tests/harness/renderApp';
import { settingsWithEmbeddings } from '@tests/msw/auth';
import { semanticApi } from '@tests/msw/semanticApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse, type RequestHandler } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

const RUN_BUTTON = 'Index library';
// One poll interval plus room for the request itself.
const POLL_TIMEOUT = 8000;

/** Settings with embeddings on, over `handlers` — the first match there wins. */
const renderSettings = (handlers: RequestHandler[] = []) => {
  worker.use(settingsWithEmbeddings(true), ...handlers);
  return renderApp({ path: '/settings' });
};

const clickRun = (screen: Screen) =>
  userEvent.click(screen.getByRole('button', { name: RUN_BUTTON }));

const expectRunReady = (screen: Screen) =>
  expect.element(screen.getByRole('button', { name: RUN_BUTTON })).toBeEnabled();

test('starting a backfill shows its progress and reports completion', async () => {
  const { handlers, advance } = semanticApi({ pendingJobs: 4 });

  const screen = await renderSettings(handlers);
  await expect.element(screen.getByRole('heading', { name: 'Search by meaning' })).toBeVisible();

  await clickRun(screen);

  await expect.element(screen.getByText('Indexing (0/4)')).toBeVisible();
  await expect.element(screen.getByRole('button', { name: RUN_BUTTON })).toBeDisabled();

  advance({ completed_jobs: 4, status: 'completed' });

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Library indexed' }), {
      timeout: POLL_TIMEOUT,
    })
    .toBeVisible();
  await expectRunReady(screen);
}, 20000);

test('a backfill already running when the page loads is shown and can be cancelled', async () => {
  const { handlers, state } = semanticApi({
    batch: aJobBatch({ total_jobs: 10, completed_jobs: 3, status: 'processing' }),
  });

  const screen = await renderSettings(handlers);

  await expect.element(screen.getByText('Indexing (3/10)')).toBeVisible();
  await expect.element(screen.getByRole('button', { name: RUN_BUTTON })).toBeDisabled();

  await userEvent.click(screen.getByRole('button', { name: 'Cancel indexing' }));

  await expectRunReady(screen);
  expect(screen.getByText('Indexing (3/10)').elements()).toHaveLength(0);
  expect(state.batch?.status).toBe('cancelled');
});

test('an already indexed library reports that there was nothing to embed', async () => {
  const { handlers } = semanticApi({ pendingJobs: 0 });

  const screen = await renderSettings(handlers);
  await clickRun(screen);

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'already indexed' }))
    .toBeVisible();
  await expectRunReady(screen);
});

test('a failed start reports the error and leaves the button ready', async () => {
  const { handlers } = semanticApi();
  // Listed ahead of the happy path, so this POST is the one that matches.
  const failingStart = http.post(
    '/api/v1/semantic/backfill',
    () => new HttpResponse(null, { status: 500 })
  );

  const screen = await renderSettings([failingStart, ...handlers]);
  await clickRun(screen);

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Failed to start indexing' }))
    .toBeVisible();
  await expectRunReady(screen);
});

test('the section is hidden when embeddings are disabled', async () => {
  worker.use(settingsWithEmbeddings(false));

  const screen = await renderApp({ path: '/settings' });
  await expect.element(screen.getByRole('heading', { name: 'Settings' })).toBeVisible();

  expect(screen.getByRole('heading', { name: 'Search by meaning' }).elements()).toHaveLength(0);
});

/**
 * Settings used to hold its own `success` state and render an inline `Alert`,
 * while every other mutation in the app reports through the snackbar.
 */
test('updating the email reports through the snackbar', async () => {
  const { handlers } = semanticApi();
  const screen = await renderSettings([
    http.post('/api/v1/users/me', () => HttpResponse.json({ id: 1, email: 'ada@example.com' })),
    ...handlers,
  ]);

  await userEvent.fill(screen.getByRole('textbox', { name: 'Email' }), 'ada@example.com');
  await userEvent.click(screen.getByRole('button', { name: 'Save email' }));

  await expect
    .element(screen.getByRole('alert').filter({ hasText: 'Email updated.' }))
    .toBeVisible();
});
