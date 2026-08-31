import { useReducedMotion } from 'motion/react';
import { useEffect, useRef } from 'react';

interface TabContentSnapOptions {
  /** False on desktop, where the nav sits beside the tab and nothing is hidden. */
  enabled: boolean;
  bookId: string | undefined;
  /** The path alone: filtering within a tab must not move the page. */
  pathname: string;
}

/**
 * Scrolls a book tab's content to the top of the viewport when the reader
 * switches tabs, and returns the ref to put on that content.
 *
 * On mobile every tab hangs below the same tall book header, so tapping a
 * different tab from the top of the page left the screen looking untouched.
 */
export const useTabContentSnap = ({ enabled, bookId, pathname }: TabContentSnapOptions) => {
  const contentRef = useRef<HTMLElement | null>(null);
  const previous = useRef({ bookId, pathname });
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    const { bookId: previousBookId, pathname: previousPathname } = previous.current;
    previous.current = { bookId, pathname };

    // Opening a book, or moving to another one, starts at that book's own top.
    if (!enabled || pathname === previousPathname || bookId !== previousBookId) return;

    const content = contentRef.current;
    if (!content) return;

    // A frame late: the router's scroll restoration runs on this same
    // navigation, and the later scroll is the one that sticks.
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
