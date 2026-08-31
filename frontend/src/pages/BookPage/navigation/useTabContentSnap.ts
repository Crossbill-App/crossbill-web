import { useReducedMotion } from 'motion/react';
import { useEffect, useRef } from 'react';

interface TabContentSnapOptions {
  /**
   * False on desktop, where the nav sits beside the tab rather than above it
   * and the tab that answered a click is already on screen.
   */
  enabled: boolean;
  bookId: string | undefined;
  /**
   * The path alone. Search params are excluded on purpose: filtering or
   * searching within a tab must not move the page under the reader.
   */
  pathname: string;
}

/**
 * Scrolls a book tab's own content up to the top of the viewport when the
 * reader switches tabs, and hands back the ref to put on that content.
 *
 * On mobile every tab hangs below the same tall book header — cover, title,
 * blurb, stats — so tapping a different tab from the top of the page changed
 * nothing the reader could see: the new tab's heading was still below the
 * fold, and only the bottom nav's selected icon had moved. Snapping past the
 * header puts that heading right under the app bar, so the tab they asked for
 * is the first thing on screen.
 */
export const useTabContentSnap = ({ enabled, bookId, pathname }: TabContentSnapOptions) => {
  const contentRef = useRef<HTMLElement | null>(null);
  const previous = useRef({ bookId, pathname });
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    const { bookId: previousBookId, pathname: previousPathname } = previous.current;
    previous.current = { bookId, pathname };

    // A tab change within one book, and nothing else: opening a book, or
    // moving to another one, should leave the reader at that book's own top.
    if (!enabled || pathname === previousPathname || bookId !== previousBookId) return;

    const content = contentRef.current;
    if (!content) return;

    // A frame late on purpose. The router's scroll restoration runs on this
    // same navigation, and whichever of the two scrolls last is the one the
    // reader sees.
    const frame = requestAnimationFrame(() => {
      content.scrollIntoView({
        behavior: prefersReducedMotion ? 'auto' : 'smooth',
        block: 'start',
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [enabled, bookId, pathname, prefersReducedMotion]);

  return contentRef;
};
