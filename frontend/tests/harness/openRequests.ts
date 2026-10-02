import type { SetupWorker } from 'msw/browser';

const isApi = (url: string | URL) =>
  new URL(url, window.location.href).pathname.startsWith('/api/');

const requestKey = (method: string, url: string | URL) =>
  `${method.toUpperCase()} ${new URL(url, window.location.href).href}`;

let open = new Set<object>();

/**
 * Only the current test's requests count: one an earlier test held on purpose
 * and never let go (`delay('infinite')`) already had its chance in that test's
 * teardown, and would otherwise hold up every teardown after it.
 */
export const startCountingForANewTest = () => {
  open = new Set();
};

const opened = () => {
  const token = {};
  const counted = open;
  counted.add(token);
  return () => counted.delete(token);
};

/** Aborted requests MSW has not picked up yet, by method and URL. */
const abortedAwaitingMsw = new Map<string, (() => void)[]>();

/**
 * An aborted request is over for the page but not for MSW: it has already gone
 * to the service worker, which hands it to whatever handlers are installed when
 * it gets there. React Query aborts a fetch whose last observer unmounts, so a
 * page torn down mid-load would otherwise read as idle at once, and its
 * requests would reach MSW after the handlers were reset — blamed, as unmocked,
 * on the next test. Keep each one open until MSW takes it.
 */
const openUntilMswTakesIt = (key: string, close: () => void) => {
  const waiting = abortedAwaitingMsw.get(key) ?? [];
  waiting.push(close);
  abortedAwaitingMsw.set(key, waiting);
};

/**
 * Counts every `/api/` request the page has sent and not yet had answered,
 * whether or not a query client knows about it: a stand-in highlight's create
 * call, for one, goes straight through axios.
 */
export const trackOpenApiRequests = () => {
  const realOpen = XMLHttpRequest.prototype.open;
  const realSend = XMLHttpRequest.prototype.send;
  const apiRequests = new WeakMap<XMLHttpRequest, string>();

  XMLHttpRequest.prototype.open = function (
    this: XMLHttpRequest,
    ...args: Parameters<XMLHttpRequest['open']>
  ) {
    const [method, url] = args;
    if (isApi(url)) apiRequests.set(this, requestKey(method, url));
    else apiRequests.delete(this);
    return realOpen.apply(this, args as Parameters<typeof realOpen>);
  } as XMLHttpRequest['open'];

  XMLHttpRequest.prototype.send = function (this: XMLHttpRequest, body) {
    const key = apiRequests.get(this);
    if (key !== undefined) {
      const close = opened();
      let aborted = false;
      this.addEventListener('abort', () => (aborted = true), { once: true });
      this.addEventListener(
        'loadend',
        () => (aborted ? openUntilMswTakesIt(key, close) : close()),
        { once: true }
      );
    }
    return realSend.call(this, body);
  };

  const realFetch = window.fetch;
  window.fetch = (input, init) => {
    const url = input instanceof Request ? input.url : input;
    if (!isApi(url)) return realFetch(input, init);
    const method = init?.method ?? (input instanceof Request ? input.method : 'GET');
    const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined);
    const answered = opened();
    const request = realFetch(input, init);
    void request.then(answered, () =>
      signal?.aborted ? openUntilMswTakesIt(requestKey(method, url), answered) : answered()
    );
    return request;
  };
};

/**
 * Counts every `/api/` request from the moment MSW takes it until it is done
 * with it, which for an aborted one is after the page stopped waiting.
 */
export const trackMswRequests = (worker: SetupWorker) => {
  const handling = new Map<string, () => void>();
  worker.events.on('request:start', ({ request, requestId }) => {
    if (!isApi(request.url)) return;
    handling.set(requestId, opened());
    abortedAwaitingMsw.get(requestKey(request.method, request.url))?.shift()?.();
  });
  worker.events.on('request:end', ({ requestId }) => {
    handling.get(requestId)?.();
    handling.delete(requestId);
  });
};

export const openApiRequests = () => open.size;
