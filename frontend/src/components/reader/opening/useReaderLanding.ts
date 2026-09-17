/**
 * Where one book should open: the place this open is a jump to, or else the
 * place the reader last got to, on whatever device they were reading.
 *
 * The reconciliation against this publication's own position list belongs to
 * the engine (`ReadiumReader.landingFor`); this only fetches the answer and
 * holds it still.
 */
import { useGetHighlightLocator } from '@/api/generated/highlights/highlights.ts';
import type {
  ChapterWithHighlights,
  HighlightLocatorResponse,
  ResumePositionResponse,
} from '@/api/generated/model';
import { useGetReadingPosition } from '@/api/generated/readium/readium.ts';
import { fromBrowserLocator, fromLocatorSchema } from '@/components/reader/api/apiLocators.ts';
import type { EbookLocation } from '@/components/reader/engine/EbookReader.ts';
import {
  chapterHintForChapter,
  chapterHintForHighlight,
  type ChapterHint,
} from '@/components/reader/opening/jumpFallback.ts';
import { useState } from 'react';

/** What an open of a book is a jump to, where the address names a place at all. */
export type ReaderTarget = { kind: 'highlight'; id: number } | { kind: 'chapter'; id: number };

/** The place the address names, a highlight taking precedence where it somehow names both. */
export const targetOf = (highlightId?: number, chapterId?: number): ReaderTarget | null => {
  if (highlightId !== undefined) return { kind: 'highlight', id: highlightId };
  return chapterId === undefined ? null : { kind: 'chapter', id: chapterId };
};

/** Where a book opens is asked afresh on every open, never taken from this tab's cache. */
const LANDING_QUERY = {
  // Opening at the beginning is the failure mode, which is the wrong place to
  // spend a retry budget when the book is what the reader came for.
  retry: false,
  staleTime: 0,
  // Not merely belt and braces with `staleTime`: on a second open in the same
  // tab a cached answer comes back as settled data and the latch below takes it
  // before the refetch lands, so the laptop would reopen where the laptop left
  // off rather than where the phone did.
  gcTime: 0,
  // Against the app's `'always'`: where a book opens is settled the moment it
  // opens, so a focus refetch could only spend a request nobody will use.
  refetchOnWindowFocus: false,
} as const;

export interface ReaderLanding {
  /** Where to open the book, or `null` to start at the beginning. */
  locator: EbookLocation | null;
  /** Whether a place exists that the server could not place in this EPUB. */
  lost: boolean;
  /** For a jump, the chapter to fall back to where the passage cannot be reached. */
  chapter: ChapterHint | null;
}

// No locator is either a place the server could not put anywhere in the EPUB it
// now holds, or an ordinary book nobody has read, which is not worth a word. A
// query that errored arrives here too, as neither.
const landingFrom = (stored: ResumePositionResponse | undefined): ReaderLanding =>
  stored?.locator
    ? { locator: fromBrowserLocator(stored.locator), lost: false, chapter: null }
    : { locator: null, lost: stored?.unresolved === true, chapter: null };

// A chapter has nothing to ask the server for: the book boots at the beginning
// and the walk to the chapter's own place in the contents finishes the landing.
const jumpFrom = (
  target: ReaderTarget,
  chapters: ChapterWithHighlights[],
  placed: HighlightLocatorResponse | undefined
): ReaderLanding =>
  target.kind === 'chapter'
    ? { locator: null, lost: false, chapter: chapterHintForChapter(chapters, target.id) }
    : {
        locator: placed?.locator ? fromLocatorSchema(placed.locator) : null,
        lost: false,
        chapter: chapterHintForHighlight(chapters, target.id),
      };

/**
 * Where this book should open, or `undefined` until the answer is in — which
 * the caller must wait for rather than boot without, because a navigator takes
 * its initial position once, at construction.
 */
export const useReaderLanding = (
  bookId: number,
  target: ReaderTarget | null,
  chapters: ChapterWithHighlights[] | undefined
): ReaderLanding | undefined => {
  const resume = useGetReadingPosition(bookId, {
    query: { ...LANDING_QUERY, enabled: target === null },
  });
  const jump = useGetHighlightLocator(target?.kind === 'highlight' ? target.id : 0, {
    query: { ...LANDING_QUERY, enabled: target?.kind === 'highlight' },
  });
  const answer =
    target === null
      ? resume.isPending
        ? undefined
        : landingFrom(resume.data)
      : // Either kind of jump wants the book's chapters: they are what it falls
        // back to, and for a chapter they are the jump itself.
        chapters === undefined || (target.kind === 'highlight' && jump.isPending)
        ? undefined
        : jumpFrom(target, chapters, jump.data);

  // Latched during render rather than in an effect, which would let the
  // un-latched answer reach the boot first. The query behind it is live, and a
  // refetch that reached the boot would rebuild the navigator and throw the
  // reader back to where they opened the book.
  const [landed, setLanded] = useState<ReaderLanding | undefined>(undefined);
  if (landed === undefined && answer !== undefined) setLanded(answer);
  return landed;
};
