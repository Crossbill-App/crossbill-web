import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { useGetHighlightLocator } from '@/api/generated/highlights/highlights.ts';
import type { LocatorSchema } from '@/api/generated/model';
import { useGetReadingPosition } from '@/api/generated/readium/readium.ts';
import { Locator, type Link } from '@readium/shared';
import { findLast } from 'lodash';
import { useMemo } from 'react';

/**
 * Where the reader left off is a fact about them, not about this browser, so
 * the answer is fetched fresh every time a book is opened rather than served
 * from whatever this tab happened to see last. `retry: false` because the
 * failure mode is opening at the beginning, which is the wrong place to spend a
 * retry budget: the book is what the reader came for.
 *
 * The same terms suit the jump: a locator derived for one highlight is derived
 * against the EPUB as it is now, and a request that fails leaves the reader
 * with a fallback rather than with nothing.
 */
const LANDING_QUERY = { retry: false, staleTime: 0, gcTime: 0 } as const;

/** The href the API gives a contents heading that links nowhere. */
const UNLINKED_HREF = '#';

/**
 * Why a landing is not the place that was asked for.
 *
 * Only ever set for a jump. A resume that cannot be restored is `lost` instead,
 * because those are different apologies: one is about a bookmark, the other
 * about the highlight the reader just clicked on.
 */
type MissedLanding = 'chapter' | 'start';

export interface ReaderLanding {
  /** Where to open the book, or `null` to start at the beginning. */
  locator: Locator | null;
  /**
   * Whether a place exists that could not be restored — the EPUB was replaced,
   * or the stored locator names a resource this publication no longer has.
   * A book nobody has read is *not* this: nothing was lost.
   */
  lost: boolean;
  /**
   * For a jump that could not be made exactly: where it landed instead. The
   * start of the highlight's own chapter where the book's contents still name
   * it, and the start of the book where they do not.
   */
  missed: MissedLanding | null;
}

/**
 * Turns a stored position into a locator this publication can actually be
 * opened at, or `null` when it names nowhere in it.
 *
 * The reconciliation is not ceremony. `EpubNavigator` resolves an initial
 * position by looking its `locations.position` up in the position list it was
 * built with, and **throws** when it finds no match — which would turn a stale
 * bookmark into the reader's whole-page "could not be opened" screen. A stored
 * position carries the position number the browser saw when it was written, one
 * derived from a KOReader xpointer carries none at all, and one derived for a
 * highlight carries none either: what a highlight's locator carries is a CSS
 * selector and the text it quotes. None of the three can be trusted to index
 * the list this publication publishes today.
 *
 * So the entry is looked up by href and progression instead: the last position
 * of that resource that begins at or before where the target is. The locator
 * that was *asked for* is what is returned, wearing that entry's position
 * number — rather than the other way round, because everything else the asked
 * for locator carries (the quoted text, the selector) is what says where in the
 * resource this is, and a position is a span of a resource rather than a place
 * in one.
 *
 * A progression is only put back when the target had one. A highlight's locator
 * does not, and writing a zero in would say "the top of this resource" over the
 * selector that says exactly where the words are.
 */
const landingFor = (target: Locator, positions: Locator[]): Locator | null => {
  const inResource = positions.filter((entry) => entry.href === target.href);
  if (inResource.length === 0) return null;
  const progression = target.locations.progression;
  const entry =
    findLast(
      inResource,
      (candidate) => (candidate.locations.progression ?? 0) <= (progression ?? 0)
    ) ?? inResource[0];
  return target.copyWithLocations({
    position: entry.locations.position,
    totalProgression: entry.locations.totalProgression,
    ...(progression === undefined ? {} : { progression }),
  });
};

/** The landing for a locator the server sent, reconciled against this publication. */
const reconciled = (stored: LocatorSchema, positions: Locator[]): Locator | null => {
  const target = Locator.deserialize(stored);
  return target ? landingFor(target, positions) : null;
};

/** Every entry of a contents tree, parents before their children. */
const flattenToc = (entries: Link[]): Link[] =>
  entries.flatMap((entry) => [entry, ...flattenToc(entry.children?.items ?? [])]);

/**
 * Where a chapter begins, as this publication's own contents and position list
 * agree on it.
 *
 * Matched on the title, because that is the only thing the two sides share. A
 * highlight knows the chapter it was made in by name — the name the EPUB's own
 * contents gave it when the book was imported — and the manifest publishes the
 * same names against hrefs. Nothing in the highlight carries an href, and its
 * `chapter_number` is an import-order number rather than an index into this
 * manifest's contents, so it cannot be indexed with either.
 */
const chapterStart = (
  chapterName: string | null,
  toc: Link[] | undefined,
  positions: Locator[]
): Locator | null => {
  if (!chapterName || !toc) return null;
  const wanted = chapterName.trim().toLowerCase();
  const entry = flattenToc(toc).find(
    (candidate) =>
      candidate.href !== UNLINKED_HREF && candidate.title?.trim().toLowerCase() === wanted
  );
  if (!entry) return null;
  // The fragment names a place inside the resource; the position list is keyed
  // by the resource itself.
  const href = entry.href.split('#')[0];
  return positions.find((position) => position.href === href) ?? null;
};

interface LandingInputs {
  bookId: number;
  /**
   * The highlight this open is a jump to, or `null` for an ordinary open.
   *
   * Must be latched by the caller at the moment the reader was opened. It is
   * where the book *opens*, and a book does not re-open because the reader
   * tapped a second highlight in it.
   */
  target: number | null;
  /** The publication's position list, or `undefined` until it has been read. */
  positions: Locator[] | undefined;
  /** The publication's contents, for the chapter a missed jump falls back to. */
  toc: Link[] | undefined;
}

/**
 * Where this book should open, resolved against the publication it will open in.
 *
 * `undefined` until the answer is in — which the caller must wait for rather
 * than boot without, because a navigator takes its initial position once, at
 * construction, and one built too early can only be corrected by a visible
 * jump after the book has already rendered somewhere else. That is why there is
 * no second path here for the jump: `?highlightId=` changes *which* place the
 * book opens at, not when or how it is opened at one.
 *
 * **Two things can say where to open, and the jump wins.** The resume answer is
 * for every device the reader owns: the browser's own stored locator, or the
 * end of the latest sitting an e-reader synced, converted from the canonical
 * xpointer (ADR-0004 §2). The jump is a highlight the reader clicked on, which
 * is an instruction rather than a memory — somebody who asked to be taken to a
 * passage is not asking to be put back where they were. A request that fails
 * outright opens the book at the beginning and says nothing, because the reader
 * came here to read and the position they lose is the one still in front of
 * them.
 *
 * **A jump that cannot be made exactly still goes somewhere useful** (M3.4,
 * #748). A highlight the server would not place, or one whose locator names a
 * resource this publication has not got, falls back to the start of the chapter
 * it was made in, and to the start of the book when even that cannot be found.
 * The chapter is worth waiting a moment for, which is why the book's own
 * details are read here: they are what name the chapter, and they have almost
 * always been fetched already by the view the reader jumped from.
 */
export const useReaderLanding = ({
  bookId,
  target,
  positions,
  toc,
}: LandingInputs): ReaderLanding | undefined => {
  const resume = useGetReadingPosition(bookId, { query: LANDING_QUERY });
  const jump = useGetHighlightLocator(target ?? 0, {
    query: { ...LANDING_QUERY, enabled: target !== null },
  });
  // Only consulted for a jump that missed, and only for the chapter name. The
  // reader itself never waits on this: the book opens without a title and
  // without decorations, and both land when they land.
  const book = useGetBookDetails(bookId);

  return useMemo(() => {
    if (positions === undefined) return undefined;

    if (target === null) {
      if (resume.isPending) return undefined;
      const stored = resume.data?.locator;
      // No locator: either the server could not place a position it holds,
      // which the reader is told about, or there is no position at all, which
      // is an ordinary state of an ordinary book and is not worth a word.
      if (!stored) return { locator: null, lost: resume.data?.unresolved === true, missed: null };
      const landing = reconciled(stored, positions);
      return { locator: landing, lost: landing === null, missed: null };
    }

    if (jump.isPending) return undefined;
    const placed = jump.data?.locator;
    const landing = placed ? reconciled(placed, positions) : null;
    if (landing) return { locator: landing, lost: false, missed: null };

    // The jump missed. The chapter it was made in is the next best place, and
    // the book has to have answered before that can be asked. `isPending` is
    // what is waited on rather than the data: a details query that failed is
    // never going to name the chapter, and holding the book shut for it would
    // cost the reader the book over a fallback.
    if (book.isPending) return undefined;
    const chapterName =
      book.data?.chapters.find((chapter) =>
        chapter.highlights.some((highlight) => highlight.id === target)
      )?.name ?? null;
    const fallback = chapterStart(chapterName, toc, positions);
    return { locator: fallback, lost: false, missed: fallback ? 'chapter' : 'start' };
  }, [
    positions,
    target,
    toc,
    resume.isPending,
    resume.data,
    jump.isPending,
    jump.data,
    book.isPending,
    book.data,
  ]);
};
