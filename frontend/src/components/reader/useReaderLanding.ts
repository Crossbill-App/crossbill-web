import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { useGetHighlightLocator } from '@/api/generated/highlights/highlights.ts';
import type { BookDetails, ChapterWithHighlights, LocatorSchema } from '@/api/generated/model';
import { useGetReadingPosition } from '@/api/generated/readium/readium.ts';
import { Locator, type Link } from '@readium/shared';
import { findLast } from 'lodash';
import { useCallback, useEffect, useMemo, useState } from 'react';

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
 *
 * `refetchOnWindowFocus` is off against an app default of `'always'`. Where a
 * book opens is settled the moment it opens — the answer is latched below and
 * cannot be acted on again — so a refetch on every return to the tab could only
 * spend a request to learn something nobody may use. It would also be a fresh
 * object for the memo to chew on for the whole life of the reader.
 */
const LANDING_QUERY = {
  retry: false,
  staleTime: 0,
  gcTime: 0,
  refetchOnWindowFocus: false,
} as const;

/**
 * How long a jump that missed waits for the book's own chapter names before
 * giving up and opening at the start.
 *
 * Only this branch waits at all, and only for a fallback. The reader is looking
 * at a skeleton while it does, and no watchdog covers this part of the boot —
 * the reader's own starts once there is something to boot — so the wait has to
 * end by itself. Long enough for an ordinary answer on a slow connection, short
 * enough that a request which is never coming back costs a moment rather than
 * the book.
 */
const CHAPTER_NAME_GRACE_MS = 3_000;

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

/** A landing, and whether it is the place that was asked for or only its resource. */
interface Reconciled {
  locator: Locator;
  /**
   * Whether the locator that was asked for said anything about where *inside*
   * its resource it was. When it did not, all this landing knows is the
   * chapter, and it must be reported as such rather than passed off as the
   * passage — see `placesWithinResource`.
   */
  exact: boolean;
}

/**
 * Whether a locator says where inside its resource it is, or only which
 * resource that is.
 *
 * The distinction is the difference between arriving at a passage and arriving
 * at a chapter, and the reader is owed the truth about which they got (M3.4,
 * #748). A locator with none of these reconciles perfectly happily — the href
 * names a resource the publication has — and lands at the top of it, which
 * looks exactly like a successful jump and is not one.
 *
 * A quote or a selector is enough: those name the words, and the navigator
 * resolves them within the resource. So is a progression or a position, which
 * name a place in it even if only approximately.
 */
const placesWithinResource = (locator: Locator): boolean =>
  locator.locations.progression !== undefined ||
  locator.locations.position !== undefined ||
  locator.locations.fragments.length > 0 ||
  locator.locations.otherLocations?.has('cssSelector') === true ||
  locator.text?.highlight !== undefined;

/**
 * Turns a locator the server sent into one this publication can actually be
 * opened at, or `null` when it names nowhere in it.
 *
 * The reconciliation is not ceremony. `EpubNavigator` resolves an initial
 * position by looking its `locations.position` up in the position list it was
 * built with, and **throws** when it finds no match — which would turn a stale
 * bookmark into the reader's whole-page "could not be opened" screen. A stored
 * position carries the position number the browser saw when it was written, and
 * one derived from a KOReader xpointer or from a highlight's xpointer carries
 * none at all: the backend computes a progression and a `cssSelector` against
 * the EPUB, and leaves `position` to whoever holds a position list. Neither can
 * be trusted to index the list this publication publishes today.
 *
 * So the entry is looked up by href and progression instead: the last position
 * of that resource that begins at or before where the target is. The locator
 * that was *asked for* is what is returned, wearing that entry's position
 * number — rather than the other way round, because everything else the asked
 * for locator carries (the quoted text, the selector, the progression) is what
 * says where in the resource this is, and a position is a span of a resource
 * rather than a place in one.
 *
 * A progression is only written back when the target had one, so that a locator
 * carrying only a selector is not told it is at the top of its resource.
 */
const landingFor = (target: Locator, positions: Locator[]): Reconciled | null => {
  const inResource = positions.filter((entry) => entry.href === target.href);
  if (inResource.length === 0) return null;
  const progression = target.locations.progression;
  const entry =
    findLast(
      inResource,
      (candidate) => (candidate.locations.progression ?? 0) <= (progression ?? 0)
    ) ?? inResource[0];
  return {
    locator: target.copyWithLocations({
      position: entry.locations.position,
      totalProgression: entry.locations.totalProgression,
      ...(progression === undefined ? {} : { progression }),
    }),
    exact: placesWithinResource(target),
  };
};

/** The landing for a locator the server sent, reconciled against this publication. */
const reconciled = (stored: LocatorSchema, positions: Locator[]): Reconciled | null => {
  const target = Locator.deserialize(stored);
  return target ? landingFor(target, positions) : null;
};

/** Every entry of a contents tree, parents before their children. */
const flattenToc = (entries: Link[]): Link[] =>
  entries.flatMap((entry) => [entry, ...flattenToc(entry.children?.items ?? [])]);

/**
 * A chapter title as it can be compared across two sources that both got it
 * from the same EPUB and neither of which preserved its spacing exactly.
 *
 * A title imported into the database and the same title in a manifest differ by
 * a non-breaking space, a line break kept from the contents markup, or a run of
 * indentation — none of which anybody meant. Collapsing them is safe in one
 * direction only: the cost of over-normalising is a chapter matched that should
 * not have been, which is caught by the ambiguity rule below; the cost of
 * under-normalising is a fallback silently lost.
 */
const comparableTitle = (title: string): string => title.replace(/\s+/g, ' ').trim().toLowerCase();

/**
 * Which chapter of the book a highlight was made in, in terms the manifest's
 * own contents can be searched with.
 *
 * The name is what the two sides share: a highlight's chapter is the title the
 * EPUB's contents gave it when the book was imported, and the manifest
 * publishes those same titles against hrefs. Nothing in a highlight carries an
 * href.
 *
 * The other two fields exist because titles repeat. "Introduction" and
 * "Conclusion" appear once per part in plenty of books, and matching on the
 * title alone lands the reader in part one every time. `chapter_number` is the
 * book's own ordering, so the *n*th chapter of that name here is the *n*th
 * entry of that name there — a correspondence that is only worth trusting when
 * both sides count the same number of them.
 */
interface ChapterHint {
  name: string;
  /** How many chapters of this book share the name and come before this one. */
  occurrence: number;
  /** How many chapters of this book carry that name at all. */
  namesakes: number;
}

/** The book's own chapter order: its numbering, and its ids where that is absent. */
const byChapterOrder = (a: ChapterWithHighlights, b: ChapterWithHighlights): number =>
  (a.chapter_number ?? Number.MAX_SAFE_INTEGER) - (b.chapter_number ?? Number.MAX_SAFE_INTEGER) ||
  a.id - b.id;

const chapterHintFor = (details: BookDetails, highlightId: number): ChapterHint | null => {
  const chapters = [...details.chapters].sort(byChapterOrder);
  const chapter = chapters.find((candidate) =>
    candidate.highlights.some((highlight) => highlight.id === highlightId)
  );
  if (!chapter?.name) return null;
  const namesakes = chapters.filter((candidate) => candidate.name === chapter.name);
  return {
    name: chapter.name,
    occurrence: namesakes.findIndex((candidate) => candidate.id === chapter.id),
    namesakes: namesakes.length,
  };
};

/**
 * Where a chapter begins, as this publication's own contents and position list
 * agree on it — or `null` where they cannot be made to agree confidently.
 *
 * One entry of that title is the easy case. Several is the case worth being
 * careful about: the reader is already having a jump go wrong, and dropping
 * them into the wrong part of the book while apologising for the *right* one
 * would be worse than the plain start of the book. So the book's own chapter
 * numbering breaks the tie, and only when both sides count the same number of
 * chapters by that name — anything else is guesswork wearing a fallback's
 * clothes.
 */
const chapterStart = (
  hint: ChapterHint | null,
  toc: Link[] | undefined,
  positions: Locator[]
): Locator | null => {
  if (!hint || !toc) return null;
  const wanted = comparableTitle(hint.name);
  if (!wanted) return null;

  const matches = flattenToc(toc).filter(
    (candidate) =>
      candidate.href !== UNLINKED_HREF && comparableTitle(candidate.title ?? '') === wanted
  );
  const entry =
    matches.length === 1
      ? matches[0]
      : matches.length === hint.namesakes
        ? matches[hint.occurrence]
        : undefined;
  if (!entry) return null;

  // The fragment names a place inside the resource; the position list is keyed
  // by the resource itself.
  const href = entry.href.split('#')[0];
  return positions.find((position) => position.href === href) ?? null;
};

/** Whether `ms` has passed since this became active. Never resets. */
const useGraceElapsed = (ms: number, active: boolean): boolean => {
  const [elapsed, setElapsed] = useState(false);
  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setElapsed(true), ms);
    return () => clearTimeout(timer);
  }, [ms, active]);
  return elapsed;
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
 * **The answer is latched, and that is a correctness property rather than an
 * optimisation.** Where a book opened is a fact about one moment, and the
 * queries behind it are live: book details are invalidated by every mutation
 * the highlight dialog makes, and a reading position is re-read on whatever
 * schedule its query keeps. Without the latch each of those hands the boot
 * effect a freshly-built `Locator` and it rebuilds the navigator — throwing the
 * reader back to where they were when they opened the book, and, once they turn
 * a page from there, writing that regression to the server as their position.
 * A landing cannot legitimately change after the book has opened at it, so it
 * does not.
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
 * #748). A highlight the server would not place, one whose locator names a
 * resource this publication has not got, and one whose locator names only a
 * resource all fall back to the start of the chapter it was made in — and to
 * the start of the book when even that cannot be found. That branch is the one
 * place the book's own details are read, because they are what name the
 * chapter; every other path here answers without them, so an ordinary open and
 * a jump that lands never wait on that query at all.
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

  // Narrowed to the one fact the fallback needs, and fetched only where it
  // could be needed. `select` is what keeps a book's whole details payload —
  // every highlight, every tag, re-fetched on every mutation the dialog makes —
  // from being a dependency of where the book opens.
  const selectChapter = useCallback(
    (details: BookDetails) => (target === null ? null : chapterHintFor(details, target)),
    [target]
  );
  const chapter = useGetBookDetails(bookId, {
    query: { enabled: target !== null, select: selectChapter },
  });
  const outOfPatience = useGraceElapsed(CHAPTER_NAME_GRACE_MS, target !== null);

  const answer = useMemo((): ReaderLanding | undefined => {
    if (positions === undefined) return undefined;

    if (target === null) {
      if (resume.isPending) return undefined;
      const stored = resume.data?.locator;
      // No locator: either the server could not place a position it holds,
      // which the reader is told about, or there is no position at all, which
      // is an ordinary state of an ordinary book and is not worth a word.
      if (!stored) return { locator: null, lost: resume.data?.unresolved === true, missed: null };
      const landing = reconciled(stored, positions);
      return { locator: landing?.locator ?? null, lost: landing === null, missed: null };
    }

    if (jump.isPending) return undefined;
    const placed = jump.data?.locator;
    const landing = placed ? reconciled(placed, positions) : null;
    if (landing?.exact) return { locator: landing.locator, lost: false, missed: null };

    // The jump missed, or landed on nothing more precise than a resource. Both
    // want the chapter, and the chapter wants the book's own names — so this is
    // the one branch that waits, and it waits only until the query settles
    // either way or the grace above runs out.
    if (chapter.isPending && !outOfPatience) return undefined;
    const fallback = chapterStart(chapter.data ?? null, toc, positions) ?? landing?.locator ?? null;
    return { locator: fallback, lost: false, missed: fallback ? 'chapter' : 'start' };
  }, [
    positions,
    target,
    toc,
    outOfPatience,
    resume.isPending,
    resume.data,
    jump.isPending,
    jump.data,
    chapter.isPending,
    chapter.data,
  ]);

  // Latched during render rather than in an effect, the way `useResetOnChange`
  // adjusts state: an effect would let the un-latched answer reach the boot
  // first, which is the whole thing being prevented.
  const [landed, setLanded] = useState<ReaderLanding | undefined>(undefined);
  if (landed === undefined && answer !== undefined) setLanded(answer);
  return landed;
};
