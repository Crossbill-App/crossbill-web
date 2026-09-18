import type {
  EbookChapterProgress,
  EbookTocEntry,
} from '@/components/reader/engine/EbookReader.ts';
import type { Locator } from '@readium/shared';
import { max, sortBy, uniq, uniqBy } from 'lodash';

/** The resource on screen in screen pages, at the current size and font. */
export interface ResourceLayout {
  pageCount: number;
  /** The page on screen, counting from 0. */
  page: number;
  /** Where each contents entry inside the resource begins, in pages from its start; 1.5 is half-way down page 1. */
  sectionStarts: number[];
}

const hrefsIn = (entries: EbookTocEntry[]): string[] =>
  entries.flatMap((entry) => [entry.href, ...hrefsIn(entry.children)]);

const bare = (href: string) => href.split('#')[0];

/**
 * The first position of every resource the contents link to, in order.
 *
 * Readium's timeline would name these, but it leaves a resource with sections
 * of its own in the contents without a position, and that is most chapters.
 */
export const chapterStartsIn = (toc: EbookTocEntry[], positions: Locator[]): number[] => {
  const linked = new Set(hrefsIn(toc).map(bare));
  const starts = uniqBy(
    positions.filter((locator) => linked.has(locator.href)),
    (locator) => locator.href
  )
    .map((locator) => locator.locations.position)
    .filter((position) => position !== undefined);
  return sortBy(uniq([1, ...starts]));
};

/** The ids of the contents entries that start part-way into the resource at `href`. */
export const sectionIdsIn = (toc: EbookTocEntry[], href: string): string[] =>
  hrefsIn(toc)
    .filter((entry) => bare(entry) === href && entry.includes('#'))
    .map((entry) => decodeURIComponent(entry.slice(entry.indexOf('#') + 1)))
    .filter(Boolean);

/**
 * Measures a paginated resource the way Readium's column snapper pages it:
 * one page is the frame's width, scrolled sideways.
 */
export const resourceLayoutIn = (frame: Window, sectionIds: string[]): ResourceLayout => {
  const root = frame.document.scrollingElement ?? frame.document.documentElement;
  const width = frame.innerWidth;
  const scrolled = Math.abs(root.scrollLeft);
  const sectionStarts = sectionIds
    .map((id) => frame.document.getElementById(id))
    .filter((element) => element !== null)
    .map((element) => (element.getBoundingClientRect().left + scrolled) / width);
  return {
    pageCount: Math.max(1, Math.round(root.scrollWidth / width)),
    page: Math.round(scrolled / width),
    sectionStarts,
  };
};

/**
 * The screen pages left in the innermost contents entry the reader is in.
 *
 * The resource on screen is measured, so an entry that ends inside it ends on
 * the page the next one begins on. An entry that runs past it into resources
 * the contents do not link to is estimated there at this resource's pages per
 * position, since those are not laid out yet.
 */
export const chapterProgressAt = (
  locator: Locator,
  layout: ResourceLayout,
  starts: number[],
  positions: Locator[]
): EbookChapterProgress | null => {
  const position = locator.locations.position;
  if (position === undefined) return null;

  // A section starting at the very top of this page is the one being read.
  const nextSection = sortBy(layout.sectionStarts).find((start) => start > layout.page + 0.01);
  if (nextSection !== undefined) {
    return { pagesLeft: Math.max(0, Math.ceil(nextSection) - 1 - layout.page) };
  }

  const inResource = positions
    .filter((candidate) => candidate.href === locator.href)
    .map((candidate) => candidate.locations.position ?? position);
  const afterResource = (max(inResource) ?? position) + 1;
  const chapterEnd = starts.find((start) => start > position) ?? positions.length + 1;
  const laterPositions = Math.max(0, chapterEnd - afterResource);
  const pagesPerPosition = layout.pageCount / Math.max(1, inResource.length);

  return {
    pagesLeft: layout.pageCount - 1 - layout.page + Math.round(laterPositions * pagesPerPosition),
  };
};
