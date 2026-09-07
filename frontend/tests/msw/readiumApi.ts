import type {
  PositionList,
  ReadingPosition,
  ReadingPositionUpdate,
  ResumePositionResponse,
  WebPublicationManifest,
} from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aManifest, aPositionList, nowhereToResume } from '../fixtures/publication';

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
const chapterDocument = (title: string, paragraphs = 1) =>
  `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>${title}</title></head>
  <body><h1>${title}</h1>${Array.from(
    { length: paragraphs },
    (_, index) => `<p>Attention is the rarest and purest form of generosity. (${index + 1})</p>`
  ).join('')}</body>
</html>`;

/**
 * How many paragraphs make a chapter longer than one screen.
 *
 * A position is a span of a resource, not a rendered page, so a chapter this
 * long paginates into several columns that all sit inside position 1 of the
 * list — which is the only way to turn a page in a test without the position
 * number changing. Books whose chapters run to more than a screenful are the
 * ordinary case rather than the exotic one; the fixture's usual one-paragraph
 * chapters are what is unrepresentative.
 */
const PARAGRAPHS_PAST_ONE_SCREEN = 120;

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
 *
 * The `onerror` vector hangs off a `data:` URL that is not a PNG rather than a
 * missing file. It has to fail to load for the handler to have its chance, and
 * a `data:` URL fails in the decoder rather than over the network — WebKit
 * issues the request for a missing file late enough that it lands after the
 * test's own handlers are gone, which the unmocked-request guard rightly calls
 * out. The vector is the same either way: an inline event handler that must not
 * survive `disarm`.
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
    <img src="data:image/png;base64,bm90LWFuLWltYWdl" onerror="parent.document.body.setAttribute('data-pwned', 'onerror')" />
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
  /**
   * Serve the first chapter long enough to paginate into several columns, so
   * that turning a page stays inside one entry of the position list.
   */
  longFirstChapter?: boolean;
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
  longFirstChapter = false,
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
    const isFirstChapter = path === 'OEBPS/chapter1.xhtml';
    const rewritten =
      hostile && isFirstChapter
        ? { body: hostileChapter(), type: 'application/xhtml+xml' }
        : longFirstChapter && isFirstChapter
          ? {
              body: chapterDocument('On Attention', PARAGRAPHS_PAST_ONE_SCREEN),
              type: 'application/xhtml+xml',
            }
          : undefined;
    const resource = rewritten ?? RESOURCES[path];
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
 * `stored` is what the `GET` answers — where the book should open, on any
 * device. It defaults to a book nobody has read anywhere, which is what every
 * test that is not about resuming wants.
 *
 * Register these after `readiumApi()` — MSW resolves newest first — when a test
 * needs to see the writes or to seed a place to resume from.
 */
export const readingPositionApi = (stored: ResumePositionResponse = nowhereToResume()) => {
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

/**
 * A book with no EPUB: the manifest 404s, which is how the app learns there is
 * none.
 *
 * The reading position still answers, as it does in production — that route
 * 404s for a book that is not the caller's, never for one that merely has
 * nothing to read — and the reader asks it in parallel with the manifest rather
 * than waiting to find out whether there is a book to resume in.
 */
export const noPublication = [
  http.post(SESSION_PATH, () => HttpResponse.json({ expires_in: 900 })),
  http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 404 })),
  ...readingPositionApi().handlers,
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
