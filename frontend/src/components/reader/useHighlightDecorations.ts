import { useGetBookHighlightLocators } from '@/api/generated/highlights/highlights.ts';
import type { Highlight } from '@/api/generated/model';
import {
  activatedHighlightId,
  decorationCoversPoint,
  EMPHASIS,
  HIGHLIGHT_DECORATION_GROUP,
  highlightDecorations,
  isPlaced,
} from '@/components/reader/decorations.ts';
import type { DecorationObserver, EpubNavigator } from '@readium/navigator';
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';

/**
 * Deriving a book's locators is the one read the reader makes that can take a
 * visible moment, so nothing waits on it, nothing repeats it, and a failure is
 * silent.
 *
 * ADR-0004 *Amendment 5* measured the worst book in the development clone at
 * 561 ms of conversion for its 54 highlights, and the cost is per highlight
 * against a flat spine — so a heavily annotated book of that shape runs into
 * seconds. Everything here follows from that number.
 *
 * `refetchOnWindowFocus` is off against an app default of `'always'`, which
 * would re-derive the whole book every time the reader came back to the tab —
 * the most expensive read in the app, repeated for a change that cannot have
 * happened. A locator moves only when the EPUB is replaced (which no screen in
 * this app can do, and which would take the manifest with it) or when the set
 * of highlights changes — and a deletion prunes this cache directly rather than
 * asking the server again, because the answer for the highlights that remain is
 * the one already in hand.
 *
 * `staleTime` is `Infinity` for the same reason: within one sitting there is no
 * event that makes a cached answer wrong, and a book reopened in a new sitting
 * gets a fresh query anyway. `retry: false` because the fallback is a book with
 * no decorations on it, which is still the book.
 */
const LOCATORS_QUERY = {
  retry: false,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
} as const;

interface HighlightDecorationsOptions {
  bookId: number;
  /**
   * The book's highlights as the book-details payload carries them, for their
   * labels — and `undefined` until that query has answered at all.
   *
   * The distinction matters: an empty array is a book with no highlights, and
   * `undefined` is a book whose highlights have not arrived. Drawing rules
   * differ (see `highlightDecorations`), and so does what may be opened.
   */
  highlights: Highlight[] | undefined;
  /** The live navigator, or `null` between boots. */
  navigatorRef: RefObject<EpubNavigator | null>;
  /** Called with the highlight a reader tapped a decoration for. */
  onActivate: (highlightId: number) => void;
  /**
   * The highlight this reader was opened to jump to, if any — brightened for a
   * moment once there is a mark on the page to brighten (M3.3, #747).
   *
   * Latched by the caller at the moment the reader opened, like the landing
   * itself: arriving at a highlight is what the emphasis is about, and a reader
   * who then taps a second highlight has not arrived anywhere.
   */
  emphasise: number | null;
  /**
   * Whether the book is on screen. Only the emphasis waits on it: a pulse run
   * over a skeleton is a pulse nobody saw, and the two are genuinely unordered
   * — the locators can answer before the first frame is built or a second after
   * it.
   */
  isPageVisible: boolean;
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
  /**
   * Whether a decoration is under this point of a frame, for the tap zones.
   * Stable, so binding it to a frame never rebuilds the navigator.
   */
  claimsPoint: (frameWindow: Window, clientX: number, clientY: number) => boolean;
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
  emphasise,
  isPageVisible,
}: HighlightDecorationsOptions): HighlightDecorations => {
  const { data } = useGetBookHighlightLocators(bookId, { query: LOCATORS_QUERY });

  // Started when there is both a mark to brighten and a page to see it on, and
  // not before either. The book and its marks arrive independently (Amendment
  // 5) in whichever order they arrive, so a pulse tied to just one of the two
  // is a pulse that sometimes runs over a skeleton and sometimes over an
  // undecorated page.
  const opacity = useEmphasisRamp(isPageVisible && isPlaced(data?.items ?? [], emphasise));

  const decorations = useMemo(
    () =>
      highlightDecorations(
        data?.items ?? [],
        highlights,
        emphasise === null || opacity === null ? null : { highlightId: emphasise, opacity }
      ),
    [data, highlights, emphasise, opacity]
  );

  // Read through refs by the callbacks below, so that everything handed to the
  // boot stays the same object for the navigator's whole life. A changing one
  // would be a changing dependency of the boot effect, and the boot effect
  // rebuilds the reader — the book would blink back to page one every time a
  // highlight was edited.
  const decorationsRef = useRef(decorations);
  const onActivateRef = useRef(onActivate);
  const highlightsRef = useRef(highlights);
  useEffect(() => {
    onActivateRef.current = onActivate;
  }, [onActivate]);
  useEffect(() => {
    highlightsRef.current = highlights;
  }, [highlights]);

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
        // A decoration whose highlight the book no longer has opens nothing:
        // the dialog reads the highlight out of the book-details payload, so
        // activating one would push a URL that renders no dialog and leave the
        // reader pressing back for a history entry they never saw. Only checked
        // once that payload has arrived — before then, nothing is known to be
        // missing.
        const known = highlightsRef.current;
        if (known !== undefined && !known.some((highlight) => highlight.id === highlightId))
          return false;
        onActivateRef.current(highlightId);
        // Claimed, so the navigator's own pager leaves the gesture alone. The
        // reader's tap zones are a separate listener and ask `claimsPoint`.
        return true;
      },
    }),
    []
  );

  const claimsPoint = useCallback(
    (frameWindow: Window, clientX: number, clientY: number) =>
      decorationsRef.current.length > 0 && decorationCoversPoint(frameWindow, clientX, clientY),
    []
  );

  return { observer, apply, claimsPoint };
};

/**
 * The tint strength of an emphasised decoration, stepping down to `null` once
 * the ramp has run.
 *
 * `null` means "no emphasis", which is what every decoration in the book gets
 * and what the emphasised one goes back to. The ramp is one-shot by
 * construction: `drawable` goes false to true once, when the locator list
 * arrives with a place for the highlight, and each step schedules the next
 * until there are none left. A step that is unmounted mid-ramp simply stops.
 */
const useEmphasisRamp = (drawable: boolean): number | null => {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!drawable || step >= EMPHASIS.opacities.length) return;
    const timer = setTimeout(() => setStep((current) => current + 1), EMPHASIS.stepMs);
    return () => clearTimeout(timer);
  }, [drawable, step]);

  if (!drawable || step >= EMPHASIS.opacities.length) return null;
  return EMPHASIS.opacities[step];
};
