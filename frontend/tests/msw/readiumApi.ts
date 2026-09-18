import type {
  CreatedHighlightResponse,
  HighlightLocatorResponse,
  PositionList,
  ReadingPosition,
  ReadingPositionUpdate,
  ResumePositionResponse,
  SelectionHighlightCreate,
  WebPublicationManifest,
} from '@/api/generated/model';
import { delay, http, HttpResponse } from 'msw';
import { aManifest, aPositionList, nowhereToResume } from '../fixtures/publication';

const MANIFEST_PATH = '/api/v1/readium/books/:bookId/manifest.json';
const POSITIONS_PATH = '/api/v1/readium/books/:bookId/positions.json';
const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const RESOURCE_PATH = '/api/v1/readium/books/:bookId/resources/*';
const POSITION_PATH = '/api/v1/readium/books/:bookId/reading-position';
const HIGHLIGHT_LOCATORS_PATH = '/api/v1/books/:bookId/highlight-locators';
const HIGHLIGHT_LOCATOR_PATH = '/api/v1/highlights/:highlightId/locator';
const HIGHLIGHTS_PATH = '/api/v1/books/:bookId/highlights';

/** An anchor half-way through chapter two, for a contents entry to start a subchapter at. */
export const CHAPTER_TWO_SECOND_HALF = 'second-half';

const PARAGRAPH = 'Attention is the rarest and purest form of generosity.';

/** A chapter as an EPUB actually ships one: XHTML, with its own namespace. */
const chapterDocument = (title: string, paragraphs = 1, anchorAt?: number) =>
  `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>${title}</title></head>
  <body><h1>${title}</h1>${Array.from(
    { length: paragraphs },
    (_, index) =>
      `<p${index === anchorAt ? ` id="${CHAPTER_TWO_SECOND_HALF}"` : ''}>${PARAGRAPH}</p>`
  ).join('')}</body>
</html>`;

/**
 * A chapter that tries to break out of its frame, by every route a document has.
 *
 * The `onerror` image is a `data:` URL because a missing file's request outlives
 * the test that provoked it.
 */
const hostileChapter = () =>
  `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>On Attention</title>
    <script>parent.document.body.setAttribute('data-pwned', 'inline-script')</script>
    <script src="evil.js"></script>
    <meta http-equiv="REFRESH" content="0; url=escape-hatch.xhtml" />
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
  // Long enough to paginate into many columns, so a test can open the book
  // part-way through a chapter rather than only at the head of one. Safe for
  // every other test because nothing here turns more than one page into it.
  'OEBPS/chapter2.xhtml': {
    body: chapterDocument('On Memory', 240, 120),
    type: 'application/xhtml+xml',
  },
  'OEBPS/style.css': { body: 'body { margin: 0; }', type: 'text/css' },
  'OEBPS/evil.js': {
    body: "parent.document.body.setAttribute('data-pwned', 'external-script')",
    type: 'text/javascript',
  },
};

/**
 * The reading-position endpoint: what the reader resumes from, and every write.
 *
 * The reader writes debounced and again on the way out, so a test asserts on
 * `writes` rather than on a spy: what matters is what reached the server.
 * Register these after `readiumApi()`, which MSW resolves newest first.
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
 * Where the book's highlights are in its EPUB. Register these after `readiumApi()`,
 * which MSW resolves newest first.
 */
export const highlightLocatorsApi = (
  items: HighlightLocatorResponse[] = [],
  { delayMs, onRequest }: { delayMs?: number; onRequest?: () => void } = {}
) => [
  http.get(HIGHLIGHT_LOCATORS_PATH, async () => {
    onRequest?.();
    // Guarded, because MSW's `delay()` with no argument is a random one.
    if (delayMs) await delay(delayMs);
    return HttpResponse.json({ items });
  }),
];

/**
 * Where each of these highlights is, one at a time; any other id 404s, as a deleted
 * highlight does. Register these after `readiumApi()`, which MSW resolves newest first.
 */
export const highlightLocatorApi = (
  items: HighlightLocatorResponse[],
  { delayMs }: { delayMs?: number } = {}
) => [
  http.get(HIGHLIGHT_LOCATOR_PATH, async ({ params }) => {
    const highlightId = Number(params.highlightId);
    if (delayMs) await delay(delayMs);
    const item = items.find((candidate) => candidate.highlight_id === highlightId);
    return item ? HttpResponse.json(item) : new HttpResponse(null, { status: 404 });
  }),
];

export interface HighlightCreationAnswer {
  status?: number;
  id?: number;
  delayMs?: number;
}

/** Register these after `readiumApi()`, which MSW resolves newest first. */
export const highlightCreationApi = (
  answers: HighlightCreationAnswer[],
  { onCreated }: { onCreated?: (id: number) => void } = {}
) => {
  const bodies: SelectionHighlightCreate[] = [];
  const handlers = [
    http.post(HIGHLIGHTS_PATH, async ({ request, params }) => {
      const body = (await request.json()) as SelectionHighlightCreate;
      const {
        status = 201,
        id = 400,
        delayMs,
      } = answers[Math.min(bodies.length, answers.length - 1)];
      bodies.push(body);
      if (delayMs) await delay(delayMs);
      if (status >= 400) return new HttpResponse(null, { status });
      onCreated?.(id);
      return HttpResponse.json(
        {
          id,
          book_id: Number(params.bookId),
          text: body.locator.text?.highlight ?? '',
          datetime: '2026-09-15 12:00:00',
        } satisfies CreatedHighlightResponse,
        { status }
      );
    }),
  ];
  return { handlers, bodies };
};

interface ReadiumApiOptions {
  manifest?: WebPublicationManifest;
  positions?: PositionList;
  /** Seconds of life the session endpoint claims for the publication cookie. */
  expiresIn?: number;
  /** Serve the first chapter as a book that attacks the page that opened it. */
  hostile?: boolean;
  /** Told about every request these handlers answer, for tests about what was sent. */
  onRequest?: (request: Request) => void;
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
  onRequest = () => {},
}: ReadiumApiOptions = {}) => [
  http.post(SESSION_PATH, ({ request }) => {
    onRequest(request);
    return HttpResponse.json({ expires_in: expiresIn });
  }),
  http.get(MANIFEST_PATH, ({ request }) => {
    onRequest(request);
    return HttpResponse.json(manifest ?? aManifest());
  }),
  http.get(POSITIONS_PATH, ({ request }) => {
    onRequest(request);
    return HttpResponse.json(positions ?? aPositionList());
  }),
  // An open reader asks where to resume and writes where it gets to, so every
  // test that opens one meets these whether or not it is about them.
  // `readingPositionApi` is the version with a place to resume from and a
  // memory of what was written.
  ...readingPositionApi().handlers,
  // And it asks where the book's highlights are, whether or not the test is about
  // them; `highlightLocatorsApi` with items is the version that has some.
  ...highlightLocatorsApi(),
  // A link into the reader at a highlight asks where that one is; unanswered, it opens at the start.
  ...highlightLocatorApi([]),
  http.get(RESOURCE_PATH, ({ request, params }) => {
    onRequest(request);
    const path = String(params[0]);
    const rewritten =
      hostile && path === 'OEBPS/chapter1.xhtml'
        ? { body: hostileChapter(), type: 'application/xhtml+xml' }
        : undefined;
    const resource = rewritten ?? RESOURCES[path];
    if (!resource) return new HttpResponse(null, { status: 404 });
    return new HttpResponse(resource.body, {
      headers: { 'Content-Type': resource.type, ETag: `"${path}"` },
    });
  }),
];

/** A book with no EPUB: the manifest 404s, which is how the app learns there is none. */
export const noPublication = [
  http.post(SESSION_PATH, () => HttpResponse.json({ expires_in: 900 })),
  http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 404 })),
  // The shell asks where to resume, and where the highlights are, before it learns
  // there is nothing to open.
  ...readingPositionApi().handlers,
  ...highlightLocatorsApi(),
];
