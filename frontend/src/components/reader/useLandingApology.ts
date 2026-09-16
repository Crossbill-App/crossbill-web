/**
 * Said once, over the open book, for a place that could not be restored or a
 * passage that could not be reached; derived from what the book reported on
 * opening rather than remembered from the landing call.
 */
import { landingOfAJump, type MissedJump } from '@/components/reader/jumpFallback.ts';
import type { EbookReaderState } from '@/components/reader/useEbookReader.ts';
import type { ReaderLanding } from '@/components/reader/useReaderLanding.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useEffect, useRef } from 'react';

/** Said once, over the open book, for a place that could not be restored. */
const LOST_THE_BOOKMARK = "Couldn't restore your last position, so the book opened at the start.";

/** Said once, over the open book, for a highlight whose passage could not be reached. */
const MISSED_JUMP_APOLOGIES: Record<MissedJump, string> = {
  chapter:
    "Couldn't find this highlight's exact place, so the book opened at the start of its chapter.",
  start: "Couldn't find this highlight's place, so the book opened at the start.",
};

export const useLandingApology = (
  book: Pick<EbookReaderState, 'status' | 'landedAt' | 'toc'>,
  landing: ReaderLanding | undefined,
  target: number | null
): void => {
  const { showSnackbar } = useSnackbar();
  const apologised = useRef(false);
  useEffect(() => {
    if (apologised.current || book.status !== 'open' || !landing) return;
    // Null only before a book is open, which the status guard already excludes.
    if (book.landedAt === null) return;
    // `'start'` with a place still on offer covers both remaining failures: a
    // locator this edition cannot place, and one the navigator refused outright
    // and which the retry therefore stopped offering.
    const lost = landing.lost || (landing.locator !== null && book.landedAt === 'start');
    const missed =
      target === null
        ? null
        : landingOfAJump(
            landing.locator,
            { landedAt: book.landedAt, toc: book.toc },
            landing.chapter
          ).missed;
    const message =
      target === null ? (lost ? LOST_THE_BOOKMARK : null) : missed && MISSED_JUMP_APOLOGIES[missed];
    if (!message) return;
    apologised.current = true;
    showSnackbar(message, 'info');
  }, [book.status, book.landedAt, book.toc, landing, target, showSnackbar]);
};
