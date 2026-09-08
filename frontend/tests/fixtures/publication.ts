import type {
  PositionList,
  ResumePositionResponse,
  WebPublicationManifest,
} from '@/api/generated/model';

/** Where a book's manifest is served from, as the API's own `self` link states it. */
const manifestHref = (bookId = 1) =>
  `${window.location.origin}/api/v1/readium/books/${bookId}/manifest.json`;

/**
 * A small but genuine Readium Web Publication Manifest.
 *
 * Written the way the backend serves one — camelCase keys, hrefs relative to
 * the manifest's own URL, an unlinked `#` heading in the table of contents —
 * so that what the navigator and our own code parse in a test is the shape
 * they will meet in production.
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

/**
 * A position list where the first chapter is several positions rather than one.
 *
 * The shape every real book has and `aPositionList` does not: a position is a
 * span of a resource, and a chapter of any length is many of them. It is what a
 * reconciliation test needs to say anything at all — against one position per
 * resource, picking the last entry at or before a progression and picking the
 * only entry are the same answer, so the arithmetic that matters is untestable.
 *
 * Chapter one is split in three at even progressions; chapter two stays whole,
 * so a test can still tell the two resources apart by page number.
 */
export const aDetailedPositionList = (): PositionList => ({
  total: 4,
  positions: [
    ...[0, 1, 2].map((index) => ({
      href: 'resources/OEBPS/chapter1.xhtml',
      type: 'application/xhtml+xml',
      locations: {
        position: index + 1,
        progression: index / 3,
        totalProgression: index / 4,
      },
    })),
    {
      href: 'resources/OEBPS/chapter2.xhtml',
      type: 'application/xhtml+xml',
      locations: { position: 4, progression: 0, totalProgression: 0.75 },
    },
  ],
});

/** What the resume endpoint answers for a book nobody has read on any device. */
export const nowhereToResume = (): ResumePositionResponse => ({
  locator: null,
  source: null,
  unresolved: false,
  xpoint: null,
  position: null,
  recorded_at: null,
});

/**
 * A place to resume from, in the second chapter of `aManifest`'s publication.
 *
 * Deliberately not where the book would open on its own, so that a test seeing
 * chapter two is seeing a restore rather than a default. `source` says which
 * reader it came from; the locator is the same shape either way, because a
 * position derived from a KOReader xpointer is converted server-side into the
 * Readium locator the navigator speaks.
 */
export const aResumePosition = (
  overrides: Partial<ResumePositionResponse> = {}
): ResumePositionResponse => ({
  ...nowhereToResume(),
  locator: {
    href: 'resources/OEBPS/chapter2.xhtml',
    type: 'application/xhtml+xml',
    locations: { position: 2, progression: 0, totalProgression: 0.5 },
  },
  source: 'web',
  xpoint: '/body/DocFragment[2]/body/div[1]/p[1]',
  position: { index: 16, char_index: 0 },
  recorded_at: '2026-03-01T09:00:00Z',
  ...overrides,
});
