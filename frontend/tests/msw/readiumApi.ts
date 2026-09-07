import type {
  PositionList,
  ReadingPosition,
  ReadingPositionUpdate,
  WebPublicationManifest,
} from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aManifest, aPositionList } from '../fixtures/publication';

const MANIFEST_PATH = '/api/v1/readium/books/:bookId/manifest.json';
const POSITIONS_PATH = '/api/v1/readium/books/:bookId/positions.json';
const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const RESOURCE_PATH = '/api/v1/readium/books/:bookId/resources/*';
const POSITION_PATH = '/api/v1/readium/books/:bookId/reading-position';

/**
 * The file a hostile chapter tries to navigate its own frame to.
 *
 * Named by nothing else in the publication, so a request for it is proof the
 * frame left the document we sanitised.
 */
export const ESCAPE_HATCH = 'escape-hatch.xhtml';

/** A chapter as an EPUB actually ships one: XHTML, with its own namespace. */
const chapterDocument = (title: string) =>
  `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>${title}</title></head>
  <body><h1>${title}</h1><p>Attention is the rarest and purest form of generosity.</p></body>
</html>`;

/**
 * A chapter that tries to break out of its frame.
 *
 * The frame is same-origin with the app and Readium runs it with
 * `allow-same-origin allow-scripts`, so any of these, if it executed, would be
 * reading and writing the app's own DOM — and could just as easily spend the
 * session. Every vector marks `document.body` so a test can see which one got
 * through: an inline script, an external script from the publication's own
 * origin, an inline event handler, and a `javascript:` URL.
 *
 * The meta refresh is the one that walks around the sanitiser rather than
 * through it: it navigates the frame to a raw publication URL, which Readium's
 * injected base element resolves straight to the API. That load is a plain
 * same-origin document — no blob, no CSP, and it never passes through the
 * fetcher that would have disarmed it.
 *
 * Its target is a file nothing else in the publication references, so a request
 * for `ESCAPE_HATCH` can only mean the frame navigated. That, rather than
 * whether the document it lands on then manages to run, is what a test can
 * observe without depending on how the frame pool happens to be timed.
 */
const hostileChapter = () =>
  `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>On Attention</title>
    <script>parent.document.body.setAttribute('data-pwned', 'inline-script')</script>
    <script src="evil.js"></script>
    <meta http-equiv="REFRESH" content="0; url=${ESCAPE_HATCH}" />
  </head>
  <body onload="parent.document.body.setAttribute('data-pwned', 'onload')">
    <h1>On Attention</h1>
    <p><a href="javascript:parent.document.body.setAttribute('data-pwned','href')">A link.</a></p>
    <img src="x.png" onerror="parent.document.body.setAttribute('data-pwned', 'onerror')" />
  </body>
</html>`;

/** The files `aManifest` names, keyed by the path the resource route receives. */
const RESOURCES: Record<string, { body: string; type: string } | undefined> = {
  'OEBPS/chapter1.xhtml': { body: chapterDocument('On Attention'), type: 'application/xhtml+xml' },
  'OEBPS/chapter2.xhtml': { body: chapterDocument('On Memory'), type: 'application/xhtml+xml' },
  'OEBPS/style.css': { body: 'body { margin: 0; }', type: 'text/css' },
  'OEBPS/evil.js': {
    body: "parent.document.body.setAttribute('data-pwned', 'external-script')",
    type: 'text/javascript',
  },
};

interface ReadiumApiOptions {
  manifest?: WebPublicationManifest;
  positions?: PositionList;
  /** Seconds of life the session endpoint claims for the publication cookie. */
  expiresIn?: number;
  /** Serve the first chapter as a book that attacks the page that opened it. */
  hostile?: boolean;
}

/**
 * The web reader's endpoints for a book that has an EPUB — resources included.
 *
 * The navigator fetches the reading order itself, so serving the chapters here
 * is what lets a test drive the real thing rather than a mock of it.
 */
export const readiumApi = ({
  manifest,
  positions,
  expiresIn = 900,
  hostile = false,
}: ReadiumApiOptions = {}) => [
  http.post(SESSION_PATH, () => HttpResponse.json({ expires_in: expiresIn })),
  http.get(MANIFEST_PATH, () => HttpResponse.json(manifest ?? aManifest())),
  http.get(POSITIONS_PATH, () => HttpResponse.json(positions ?? aPositionList())),
  // An open reader writes where it is, so every test that opens one meets these
  // whether or not it is about them. `readingPositionApi` is the version that
  // remembers what was written.
  ...readingPositionApi().handlers,
  http.get(RESOURCE_PATH, ({ params }) => {
    const path = String(params[0]);
    const resource =
      hostile && path === 'OEBPS/chapter1.xhtml'
        ? { body: hostileChapter(), type: 'application/xhtml+xml' }
        : RESOURCES[path];
    if (!resource) return new HttpResponse(null, { status: 404 });
    return new HttpResponse(resource.body, {
      headers: { 'Content-Type': resource.type, ETag: `"${path}"` },
    });
  }),
];

/**
 * The reading-position endpoints, remembering every write.
 *
 * The reader writes debounced and again on the way out, so a test asserts on
 * `writes` rather than on a spy: what matters is what reached the server and
 * what it said, not which code path sent it.
 *
 * Register these after `readiumApi()` — MSW resolves newest first — when a test
 * needs to see the writes.
 */
export const readingPositionApi = (stored: ReadingPosition | null = null) => {
  const writes: ReadingPositionUpdate[] = [];
  const handlers = [
    http.get(POSITION_PATH, () => HttpResponse.json(stored)),
    http.put(POSITION_PATH, async ({ request }) => {
      const update = (await request.json()) as ReadingPositionUpdate;
      writes.push(update);
      return HttpResponse.json({
        locator: update.locator,
        xpoint: '/body/DocFragment[1]/body/div[1]/p[1]',
        position: { index: 1, char_index: 0 },
        updated_at: update.recorded_at,
      } satisfies ReadingPosition);
    }),
  ];
  return { handlers, writes };
};

/** A book with no EPUB: the manifest 404s, which is how the app learns there is none. */
export const noPublication = [
  http.post(SESSION_PATH, () => HttpResponse.json({ expires_in: 900 })),
  http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 404 })),
];

/**
 * The session endpoint refusing exactly once, as it does when the access token
 * has just expired: the next attempt, carrying a refreshed token, is answered
 * by whichever session handler was registered before this one.
 */
export const sessionUnauthorizedOnce = http.post(
  SESSION_PATH,
  () => new HttpResponse(null, { status: 401 }),
  { once: true }
);
