import { AXIOS_INSTANCE } from '@/api/axios-instance';
import { clearTokens } from '@/api/token-manager';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { cleanup } from 'vitest-browser-react';
import { worker } from './msw/worker';

// Relative URLs, so MSW handlers can be written against `/api/v1/...` paths.
AXIOS_INSTANCE.defaults.baseURL = '';

const unhandledRequests: string[] = [];

beforeAll(async () => {
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

afterEach(() => {
  cleanup();
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
