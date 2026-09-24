const isApi = (url: string | URL) =>
  new URL(url, window.location.href).pathname.startsWith('/api/');

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

/**
 * Counts every `/api/` request the page has sent and not yet had answered,
 * whether or not a query client knows about it: a stand-in highlight's create
 * call, for one, goes straight through axios.
 */
export const trackOpenApiRequests = () => {
  const realOpen = XMLHttpRequest.prototype.open;
  const realSend = XMLHttpRequest.prototype.send;
  const apiRequests = new WeakSet<XMLHttpRequest>();

  XMLHttpRequest.prototype.open = function (
    this: XMLHttpRequest,
    ...args: Parameters<XMLHttpRequest['open']>
  ) {
    if (isApi(args[1])) apiRequests.add(this);
    else apiRequests.delete(this);
    return realOpen.apply(this, args as Parameters<typeof realOpen>);
  } as XMLHttpRequest['open'];

  XMLHttpRequest.prototype.send = function (this: XMLHttpRequest, body) {
    if (apiRequests.has(this)) this.addEventListener('loadend', opened(), { once: true });
    return realSend.call(this, body);
  };

  const realFetch = window.fetch;
  window.fetch = (input, init) => {
    const url = input instanceof Request ? input.url : input;
    if (!isApi(url)) return realFetch(input, init);
    const answered = opened();
    const request = realFetch(input, init);
    void request.finally(answered).catch(() => undefined);
    return request;
  };
};

export const openApiRequests = () => open.size;
