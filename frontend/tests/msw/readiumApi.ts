import type { PositionList, WebPublicationManifest } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aManifest, aPositionList } from '../fixtures/publication';

const MANIFEST_PATH = '/api/v1/readium/books/:bookId/manifest.json';
const POSITIONS_PATH = '/api/v1/readium/books/:bookId/positions.json';
const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const RESOURCE_PATH = '/api/v1/readium/books/:bookId/resources/*';

/** A chapter as an EPUB actually ships one: XHTML, with its own namespace. */
const chapterDocument = (title: string) =>
  `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>${title}</title></head>
  <body><h1>${title}</h1><p>Attention is the rarest and purest form of generosity.</p></body>
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
];
