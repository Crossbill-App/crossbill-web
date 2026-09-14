import type {
  HighlightLocatorResponse,
  PositionList,
  ResumePositionResponse,
  WebPublicationManifest,
} from '@/api/generated/model';

const manifestHref = (bookId = 1) =>
  `${window.location.origin}/api/v1/readium/books/${bookId}/manifest.json`;

/**
 * A small but genuine Readium Web Publication Manifest.
 *
 * Written the way the backend serves one: camelCase keys, hrefs relative to the
 * manifest's own URL, and an unlinked `#` heading in the table of contents.
 */
export const aManifest = (
  overrides: Partial<WebPublicationManifest> = {}
): WebPublicationManifest => ({
  metadata: {
    title: 'The Pragmatic Reader',
    author: 'Ada Lovelace',
    language: 'en',
    identifier: 'urn:uuid:pragmatic-reader',
  },
  links: [
    { href: manifestHref(), rel: 'self', type: 'application/webpub+json' },
    {
      href: 'positions.json',
      rel: 'http://readium.org/position-list',
      type: 'application/vnd.readium.position-list+json',
    },
  ],
  readingOrder: [
    { href: 'resources/OEBPS/chapter1.xhtml', type: 'application/xhtml+xml' },
    { href: 'resources/OEBPS/chapter2.xhtml', type: 'application/xhtml+xml' },
  ],
  resources: [{ href: 'resources/OEBPS/style.css', type: 'text/css' }],
  toc: [
    { href: 'resources/OEBPS/chapter1.xhtml', title: 'On Attention' },
    {
      // A part heading links nowhere; its chapters do.
      href: '#',
      title: 'Part two',
      children: [{ href: 'resources/OEBPS/chapter2.xhtml', title: 'On Memory' }],
    },
  ],
  ...overrides,
});

/** The position list the manifest's `position-list` link resolves to. */
export const aPositionList = (overrides: Partial<PositionList> = {}): PositionList => ({
  total: 2,
  positions: [
    {
      href: 'resources/OEBPS/chapter1.xhtml',
      type: 'application/xhtml+xml',
      locations: { position: 1, progression: 0, totalProgression: 0 },
    },
    {
      href: 'resources/OEBPS/chapter2.xhtml',
      type: 'application/xhtml+xml',
      locations: { position: 2, progression: 0, totalProgression: 0.5 },
    },
  ],
  ...overrides,
});

/** The answer for a book nobody has opened anywhere, which is not a lost place. */
export const nowhereToResume = (): ResumePositionResponse => ({
  locator: null,
  source: null,
  unresolved: false,
  recorded_at: null,
});

/**
 * A place part-way through the second chapter of `aManifest`'s publication.
 *
 * Deliberately not where the book would open on its own, so that a test seeing
 * chapter two is seeing a place restored rather than a default.
 */
export const aResumePosition = (
  overrides: Partial<ResumePositionResponse> = {}
): ResumePositionResponse => ({
  locator: {
    href: 'resources/OEBPS/chapter2.xhtml',
    type: 'application/xhtml+xml',
    locations: { position: 2, progression: 0.5, totalProgression: 0.75 },
  },
  source: 'web',
  unresolved: false,
  recorded_at: '2026-09-01T19:30:00Z',
  ...overrides,
});

/**
 * A position list where the second chapter is several positions rather than one.
 *
 * Against one position per resource, "the last entry at or before a progression"
 * and "the only entry" are the same answer, so the arithmetic is untestable.
 * Chapter two is the split one because it is the chapter served as many pages;
 * chapter one stays whole, so a test can tell the resources apart by page number.
 */
export const aDetailedPositionList = (): PositionList => ({
  total: 4,
  positions: [
    {
      href: 'resources/OEBPS/chapter1.xhtml',
      type: 'application/xhtml+xml',
      locations: { position: 1, progression: 0, totalProgression: 0 },
    },
    ...[0, 1, 2].map((index) => ({
      href: 'resources/OEBPS/chapter2.xhtml',
      type: 'application/xhtml+xml',
      locations: {
        position: index + 2,
        progression: index / 3,
        totalProgression: 0.25 + index / 4,
      },
    })),
  ],
});

/** A highlight the server placed over the quoted words of chapter one's paragraph. */
export const aHighlightLocator = (highlightId: number): HighlightLocatorResponse => ({
  highlight_id: highlightId,
  locator: {
    href: 'resources/OEBPS/chapter1.xhtml',
    type: 'application/xhtml+xml',
    locations: { progression: 0, cssSelector: 'p' },
    text: { highlight: 'rarest and purest' },
  },
});

/** A highlight the server could not find anywhere in the EPUB. */
export const anUnplacedHighlight = (highlightId: number): HighlightLocatorResponse => ({
  highlight_id: highlightId,
  locator: null,
  unavailable: 'unresolved',
});
