import type { LocatorSchema } from '@/api/generated/model';
import { useGetReadingPosition } from '@/api/generated/readium/readium.ts';
import type { Locator } from '@readium/shared';
import { findLast } from 'lodash';
import { useMemo } from 'react';

/**
 * Where the reader left off is a fact about them, not about this browser, so
 * the answer is fetched fresh every time a book is opened rather than served
 * from whatever this tab happened to see last. `retry: false` because the
 * failure mode is opening at the beginning, which is the wrong place to spend a
 * retry budget: the book is what the reader came for.
 */
const RESUME_QUERY = { retry: false, staleTime: 0, gcTime: 0 } as const;

export interface ReaderResume {
  /** Where to open the book, or `null` to start at the beginning. */
  locator: Locator | null;
  /**
   * Whether a place exists that could not be restored — the EPUB was replaced,
   * or the stored locator names a resource this publication no longer has.
   * A book nobody has read is *not* this: nothing was lost.
   */
  lost: boolean;
}

/**
 * Turns a stored position into a locator this publication can actually be
 * opened at, or `null` when it names nowhere in it.
 *
 * The reconciliation is not ceremony. `EpubNavigator` resolves an initial
 * position by looking its `locations.position` up in the position list it was
 * built with, and **throws** when it finds no match — which would turn a stale
 * bookmark into the reader's whole-page "could not be opened" screen. A stored
 * position carries the position number the browser saw when it was written, and
 * one derived from a KOReader xpointer carries none at all, so neither can be
 * trusted to index the list this publication publishes today.
 *
 * So the entry is looked up by href and progression instead: the last position
 * of that resource that begins at or before where the reader was. That entry
 * supplies the position number the navigator needs and the page number the
 * chrome shows, and the stored progression is put back on top of it so the
 * reader lands where they were rather than at the top of the page containing
 * them.
 */
const landingFor = (stored: LocatorSchema, positions: Locator[]): Locator | null => {
  const inResource = positions.filter((entry) => entry.href === stored.href);
  if (inResource.length === 0) return null;
  const progression = stored.locations?.progression ?? 0;
  const landing =
    findLast(inResource, (entry) => (entry.locations.progression ?? 0) <= progression) ??
    inResource[0];
  return landing.copyWithLocations({ progression });
};

/**
 * Where this book should open, resolved against the publication it will open in.
 *
 * `undefined` until the answer is in — which the caller must wait for rather
 * than boot without, because a navigator takes its initial position once, at
 * construction, and one built too early can only be corrected by a visible
 * jump after the book has already rendered somewhere else.
 *
 * The server answers for every device the reader owns: the browser's own stored
 * locator, or the end of the latest sitting an e-reader synced, converted from
 * the canonical xpointer (ADR-0004 §2). A request that fails outright opens the
 * book at the beginning and says nothing, because the reader came here to read
 * and the position they lose is the one still in front of them.
 */
export const useResumeLocator = (
  bookId: number,
  positions: Locator[] | undefined
): ReaderResume | undefined => {
  const { data, isPending } = useGetReadingPosition(bookId, { query: RESUME_QUERY });

  return useMemo(() => {
    if (isPending || positions === undefined) return undefined;
    const stored = data?.locator;
    // No locator: either the server could not place a position it holds, which
    // the reader is told about, or there is no position at all, which is an
    // ordinary state of an ordinary book and is not worth a word.
    if (!stored) return { locator: null, lost: data?.unresolved === true };
    const landing = landingFor(stored, positions);
    return { locator: landing, lost: landing === null };
  }, [data, isPending, positions]);
};
