/**
 * The book's contents as both the drawer and the jump fallback read them.
 */
import type { EbookLocation, EbookTocEntry } from '@/components/reader/engine/EbookReader.ts';

/** The href a manifest gives a heading that groups chapters and links nowhere — a part title, say. */
const UNLINKED_HREF = '#';

/** Whether a contents entry is somewhere to go, rather than a heading over the entries below it. */
export const isNavigable = (entry: EbookTocEntry): boolean => entry.href !== UNLINKED_HREF;

/** Every entry of a nested contents tree, parents before their children. */
export const flattenToc = (entries: EbookTocEntry[]): EbookTocEntry[] =>
  entries.flatMap((entry) => [entry, ...flattenToc(entry.children)]);

/** The contents entry as a place to go to, fragment and all. */
export const tocEntryLocation = (entry: EbookTocEntry): EbookLocation => ({
  href: entry.href,
  type: entry.type,
  locations: {},
});
