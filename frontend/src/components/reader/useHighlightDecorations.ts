import type { Highlight } from '@/api/generated/model';
import { useGetBookHighlightLocators } from '@/api/generated/readium/readium.ts';
import {
  activatedHighlightId,
  HIGHLIGHT_DECORATION_GROUP,
  highlightDecorations,
} from '@/components/reader/decorations.ts';
import type { DecorationObserver, EpubNavigator } from '@readium/navigator';
import { useCallback, useEffect, useMemo, useRef, type RefObject } from 'react';

/**
 * Deriving a book's locators is the one read the reader makes that can take a
 * visible moment, so nothing waits on it and a failure is silent.
 *
 * ADR-0004 *Amendment 5* measured the worst book in the development clone at
 * 561 ms of conversion for its 54 highlights, and the cost is per highlight
 * against a flat spine — so a heavily annotated book of that shape runs into
 * seconds. `retry: false` because the fallback is a book with no decorations on
 * it, which is still the book: spending a retry budget on the marks would be
 * spending it on the wrong thing.
 */
const LOCATORS_QUERY = { retry: false } as const;

interface HighlightDecorationsOptions {
  bookId: number;
  /**
   * The book's highlights as the book-details payload carries them, for their
   * labels. Empty until that query answers, which costs the decorations their
   * colour and never their place.
   */
  highlights: Highlight[];
  /** The live navigator, or `null` between boots. */
  navigatorRef: RefObject<EpubNavigator | null>;
  /** Called with the highlight a reader tapped a decoration for. */
  onActivate: (highlightId: number) => void;
}

export interface HighlightDecorations {
  /**
   * Registered on the group at boot, before the first frame exists.
   *
   * It has to carry `onDecorationActivated` from the start: the navigator turns
   * activation on for a group only when an observer that handles it is
   * registered, so a placeholder observer would leave every decoration in the
   * book inert.
   */
  observer: DecorationObserver;
  /**
   * Hand the navigator the current set. Stable, and safe to call before
   * `load()` or with nothing to draw.
   */
  apply: () => void;
}

/**
 * Draws a book's highlights on its pages, and opens one when it is tapped.
 *
 * **Nothing here is on the path to the book appearing.** The locators are a
 * query of their own, the navigator boots without them, and decorations arrive
 * whenever they arrive — usually while the reader is still on the first page,
 * occasionally a second or two later. That is the shape *Amendment 5* asks for:
 * a book held behind its own annotations would be the worse failure.
 *
 * **Which frame a decoration lands in is Readium's problem, not ours.**
 * `applyDecorations` stores the whole set and routes each one to the frame
 * whose resource its `locator.href` names, and it re-applies a resource's own
 * decorations whenever a frame reports itself loaded. So this applies the book
 * entire, once, and a page turn into a chapter that was never on screen draws
 * its highlights without anything here running again. It is also why M2.2's
 * known limitation — two-column desktop layouts report only `_cframes[0]`
 * through `frameLoaded` — costs the decorations nothing: the navigator sends
 * ops to every frame in the pool, not only the one that reported.
 *
 * The one thing `frameLoaded` is still needed for is the opposite order: a
 * locator list that answered before there was a navigator to give it to.
 */
export const useHighlightDecorations = ({
  bookId,
  highlights,
  navigatorRef,
  onActivate,
}: HighlightDecorationsOptions): HighlightDecorations => {
  const { data } = useGetBookHighlightLocators(bookId, { query: LOCATORS_QUERY });

  const decorations = useMemo(
    () => highlightDecorations(data?.items ?? [], highlights),
    [data, highlights]
  );

  // Read through a ref by `apply`, so that the callback handed to the boot
  // stays the same object for the navigator's whole life. A changing one would
  // be a changing dependency of the boot effect, and the boot effect rebuilds
  // the reader — the book would blink back to page one every time a highlight
  // was edited.
  const decorationsRef = useRef(decorations);
  const onActivateRef = useRef(onActivate);
  useEffect(() => {
    onActivateRef.current = onActivate;
  }, [onActivate]);

  const apply = useCallback(() => {
    navigatorRef.current?.applyDecorations(decorationsRef.current, HIGHLIGHT_DECORATION_GROUP);
  }, [navigatorRef]);

  // The refresh path. `applyDecorations` diffs the new set against the old and
  // issues only the differences, so a note edited in the dialog redraws one
  // decoration and a deleted highlight removes one — on every frame the pool
  // currently holds. Frames that are not on screen are brought up to date by
  // the navigator when they next load, which is soon enough for a page nobody
  // is looking at.
  useEffect(() => {
    decorationsRef.current = decorations;
    apply();
  }, [decorations, apply]);

  const observer = useMemo<DecorationObserver>(
    () => ({
      onDecorationActivated: ({ decoration }) => {
        const highlightId = activatedHighlightId(decoration.id);
        if (highlightId === null) return false;
        onActivateRef.current(highlightId);
        // Claimed, so the tap that opened the highlight is not also a page turn.
        return true;
      },
    }),
    []
  );

  return { observer, apply };
};
