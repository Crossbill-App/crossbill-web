import type { ChapterWithHighlights } from '@/api/generated/model';
import type {
  EbookLocation,
  EbookTocEntry,
  OpenedEbook,
} from '@/components/reader/engine/EbookReader.ts';
import { flattenToc, isNavigable, tocEntryLocation } from '@/components/reader/toc.ts';

/** Where a jump that could not reach its passage went instead. */
export type MissedJump = 'chapter' | 'start';

/** The chapter a highlight was made in, as the book's own chapter list names and counts it. */
export interface ChapterHint {
  title: string;
  /** Its index among the book's chapters of the same title. */
  occurrence: number;
  namesakes: number;
}

interface JumpLanding {
  destination: EbookLocation | null;
  missed: MissedJump | null;
}

// The database and the manifest both copied the title out of the EPUB, and
// neither kept its spacing exactly.
const comparableTitle = (title: string) => title.replace(/\s+/g, ' ').trim().toLowerCase();

const byBookOrder = (a: ChapterWithHighlights, b: ChapterWithHighlights) =>
  (a.chapter_number ?? Number.MAX_SAFE_INTEGER) - (b.chapter_number ?? Number.MAX_SAFE_INTEGER) ||
  a.id - b.id;

// A locator with none of these still opens, at the top of its resource, which
// looks exactly like arriving at the passage.
const placesWithinResource = ({ locations, text }: EbookLocation) =>
  locations.progression !== undefined ||
  locations.cssSelector !== undefined ||
  text?.highlight !== undefined;

/** The chapter holding a highlight, or null where it sits in none or in one without a title. */
export const chapterHintFor = (
  chapters: ChapterWithHighlights[],
  highlightId: number
): ChapterHint | null => {
  const ordered = [...chapters].sort(byBookOrder);
  const chapter = ordered.find((candidate) =>
    candidate.highlights.some((highlight) => highlight.id === highlightId)
  );
  const title = comparableTitle(chapter?.name ?? '');
  if (!chapter || !title) return null;
  const namesakes = ordered.filter((candidate) => comparableTitle(candidate.name) === title);
  return { title, occurrence: namesakes.indexOf(chapter), namesakes: namesakes.length };
};

const chapterEntry = (toc: EbookTocEntry[], hint: ChapterHint | null) => {
  if (!hint) return undefined;
  const matches = flattenToc(toc).filter(
    (entry) => isNavigable(entry) && comparableTitle(entry.title) === hint.title
  );
  if (matches.length === 1) return matches[0];
  // Several pair up by order only where both sides count the same number of them.
  return matches.length === hint.namesakes ? matches[hint.occurrence] : undefined;
};

/** Where a jump should finish once the book is open, and what it missed on the way. */
export const landingOfAJump = (
  locator: EbookLocation | null,
  opened: Pick<OpenedEbook, 'landedAt' | 'toc'>,
  chapter: ChapterHint | null
): JumpLanding => {
  if (locator && opened.landedAt === 'requested') {
    return placesWithinResource(locator)
      ? { destination: locator, missed: null }
      : { destination: null, missed: 'chapter' };
  }
  const entry = chapterEntry(opened.toc, chapter);
  return entry
    ? { destination: tocEntryLocation(entry), missed: 'chapter' }
    : { destination: null, missed: 'start' };
};
