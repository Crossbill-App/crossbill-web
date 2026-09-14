import type { PositionList, WebPublicationManifest } from '@/api/generated/model';

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
