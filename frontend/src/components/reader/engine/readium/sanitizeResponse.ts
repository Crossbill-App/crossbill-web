/**
 * Strips a publication's own JavaScript before Readium ever frames it.
 *
 * Readium frames each chapter as a same-origin `blob:` document with
 * `allow-same-origin allow-scripts`, so a `<script>` in a book would run as the
 * signed-in user. `script-src blob:` keeps Readium's own injected scripts —
 * they are `blob:` URLs — and nothing else; removing `allow-scripts` would kill
 * those injectables too.
 */

// `child-src`/`object-src` are closed because a nested browsing context loaded
// from the API origin would be a fresh same-origin document carrying no policy.
const CONTENT_POLICY = ['script-src blob:', "object-src 'none'", "child-src 'none'"].join('; ');

const parserTypeFor = (contentType: string): DOMParserSupportedType | null => {
  const type = contentType.split(';')[0].trim().toLowerCase();
  if (type === 'application/xhtml+xml') return 'application/xhtml+xml';
  if (type === 'text/html') return 'text/html';
  return null;
};

const isEventHandler = (name: string) => name.toLowerCase().startsWith('on');

const isJavascriptUrl = (value: string) => /^\s*javascript:/i.test(value);

const disarm = (doc: Document): void => {
  doc.querySelectorAll('script').forEach((script) => script.remove());

  // A declarative refresh resolves against the base Readium injects and lands
  // the frame on a plain API response: no blob, no policy, never sanitised.
  doc.querySelectorAll('meta').forEach((meta) => {
    const pragma = meta.getAttribute('http-equiv')?.trim().toLowerCase();
    if (pragma === 'refresh') meta.remove();
  });

  doc.querySelectorAll('*').forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      const isUrlAttribute = attribute.name === 'href' || attribute.name === 'src';
      if (isEventHandler(attribute.name) || (isUrlAttribute && isJavascriptUrl(attribute.value))) {
        element.removeAttribute(attribute.name);
      }
    }
  });
};

const sanitize = (text: string, parserType: DOMParserSupportedType): string => {
  const doc = new DOMParser().parseFromString(text, parserType);
  // A document that does not parse is Readium's to complain about, in its own
  // words, rather than ours to hand back as a mangled serialisation.
  if (doc.querySelector('parsererror')) return text;

  disarm(doc);

  const head = doc.head as HTMLHeadElement | null;
  if (head) {
    const meta = doc.createElement('meta');
    meta.setAttribute('http-equiv', 'Content-Security-Policy');
    meta.setAttribute('content', CONTENT_POLICY);
    head.prepend(meta);
  }

  return new XMLSerializer().serializeToString(doc);
};

/** Returns the response with any markup document in it disarmed; anything else untouched. */
export const sanitizeResponse = async (response: Response): Promise<Response> => {
  const parserType = parserTypeFor(response.headers.get('content-type') ?? '');
  if (!response.ok || parserType === null) return response;

  return new Response(sanitize(await response.text(), parserType), {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
};
