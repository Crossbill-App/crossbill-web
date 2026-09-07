import { AXIOS_INSTANCE } from '@/api/axios-instance';
import { API_BASE_URL } from '@/api/base-url';
import { clearTokens } from '@/api/token-manager';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { cleanup } from 'vitest-browser-react';
import { pendingQueryClients } from './harness/renderApp';
import { worker } from './msw/worker';

// Relative URLs, so MSW handlers can be written against `/api/v1/...` paths.
// Already the default; pinned here so the handlers do not depend on it.
AXIOS_INSTANCE.defaults.baseURL = '';

const unhandledRequests: string[] = [];

beforeAll(async () => {
  // The axios default above can be reassigned; this one cannot — components
  // build URLs from a constant compiled out of `import.meta.env`, so a leaked
  // env var can only be caught, not corrected. Left unchecked it shows up as a
  // puzzling unmocked-request failure, or as a real request to a live backend.
  if (API_BASE_URL !== '') {
    throw new Error(
      `API_BASE_URL is ${JSON.stringify(API_BASE_URL)}, not ''. An environment ` +
        'variable reached the test build; see envPrefix in vitest.config.ts.'
    );
  }

  await worker.start({
    quiet: true,
    // MSW's own 'error' strategy only fails the request, which a component can
    // swallow. Recording them and failing in afterEach means a test can never
    // pass while silently talking to an endpoint nobody mocked.
    onUnhandledRequest(request, print) {
      const url = new URL(request.url);
      if (!url.pathname.startsWith('/api/')) return;
      unhandledRequests.push(`${request.method} ${url.pathname}`);
      print.error();
    },
  });
});

/**
 * Bounded, never-throwing wait for one `QueryClient` to have nothing in
 * flight. Deliberately not `expect.poll`: a client that is *never* going to
 * settle (a genuinely stuck request) must fall through to the unmocked-request
 * check below rather than fail the teardown itself with a timeout.
 */
async function waitForIdle(
  client: (typeof pendingQueryClients)[number],
  timeoutMs = 2000,
  intervalMs = 20
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  // Always yield at least once before the first check: a query mounted this
  // tick (e.g. a dialog that just opened) may not have dispatched its fetch
  // yet, so `isFetching()` can still read 0 the instant `cleanup()` returns,
  // even though a request is about to go out.
  do {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  } while ((client.isFetching() > 0 || client.isMutating() > 0) && Date.now() < deadline);
}

afterEach(async () => {
  cleanup();

  // Unmounting stops any query's own refetch scheduling, but a request already
  // dispatched before unmount can still be in flight for a moment after. Give
  // every client this test created a bounded chance to finish before the
  // handlers it was relying on disappear underneath it.
  const clients = pendingQueryClients.splice(0);
  await Promise.all(clients.map((client) => waitForIdle(client)));

  worker.resetHandlers();
  clearTokens();

  const unhandled = unhandledRequests.splice(0);
  if (unhandled.length > 0) {
    throw new Error(
      `Unmocked request(s): ${unhandled.join(', ')}. Add a handler under tests/msw/.`
    );
  }
});

afterAll(() => {
  worker.stop();
});
