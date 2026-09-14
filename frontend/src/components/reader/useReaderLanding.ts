/**
 * Where one book should open: the place the reader last got to, on whatever
 * device they were reading.
 *
 * The reconciliation against this publication's own position list belongs to
 * the engine (`ReadiumReader.landingFor`); this only fetches the answer and
 * holds it still.
 */
import type { BrowserLocatorSchema, ResumePositionResponse } from '@/api/generated/model';
import { useGetReadingPosition } from '@/api/generated/readium/readium.ts';
import type { EbookLocation } from '@/components/reader/EbookReader.ts';
import { useState } from 'react';

/** Where the reader left off is a fact about *them*, not about this tab. */
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

interface ReaderLanding {
  /** Where to open the book, or `null` to start at the beginning. */
  locator: EbookLocation | null;
  /** Whether a place exists that the server could not place in this EPUB. */
  lost: boolean;
}

/** The API's locator in the engine's terms, whose absences are `undefined`. */
const toEbookLocation = (stored: BrowserLocatorSchema): EbookLocation => ({
  href: stored.href,
  type: stored.type,
  title: stored.title ?? undefined,
  locations: {
    position: stored.locations?.position ?? undefined,
    progression: stored.locations?.progression ?? undefined,
    totalProgression: stored.locations?.totalProgression ?? undefined,
    fragments: stored.locations?.fragments ?? undefined,
  },
});

// No locator is either a place the server could not put anywhere in the EPUB it
// now holds, or an ordinary book nobody has read, which is not worth a word. A
// query that errored arrives here too, as neither.
const landingFrom = (stored: ResumePositionResponse | undefined): ReaderLanding =>
  stored?.locator
    ? { locator: toEbookLocation(stored.locator), lost: false }
    : { locator: null, lost: stored?.unresolved === true };

/**
 * Where this book should open, or `undefined` until the answer is in — which
 * the caller must wait for rather than boot without, because a navigator takes
 * its initial position once, at construction.
 */
export const useReaderLanding = (bookId: number): ReaderLanding | undefined => {
  const resume = useGetReadingPosition(bookId, { query: LANDING_QUERY });
  const answer = resume.isPending ? undefined : landingFrom(resume.data);

  // Latched during render rather than in an effect, which would let the
  // un-latched answer reach the boot first. The query behind it is live, and a
  // refetch that reached the boot would rebuild the navigator and throw the
  // reader back to where they opened the book.
  const [landed, setLanded] = useState<ReaderLanding | undefined>(undefined);
  if (landed === undefined && answer !== undefined) setLanded(answer);
  return landed;
};
