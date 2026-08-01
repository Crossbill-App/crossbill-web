import { animate, useReducedMotion } from 'motion/react';
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { CAROUSEL_ITEM_SELECTOR } from './CarouselItem';

const PAGE_TRANSITION = {
  duration: 0.45,
  ease: [0.32, 0.72, 0, 1] as [number, number, number, number],
};

const SETTLE_TRANSITION = {
  type: 'spring' as const,
  stiffness: 400,
  damping: 45,
};

/** Residual offset below which a settle would be imperceptible jitter. */
const SNAP_THRESHOLD_PX = 4;

/** Fallback idle window for browsers without `scrollend`. */
const SCROLL_IDLE_MS = 120;

export interface CarouselScroll {
  viewportRef: RefObject<HTMLDivElement | null>;
  isOverflowing: boolean;
  canScrollBack: boolean;
  canScrollForward: boolean;
  scrollByPage: (direction: -1 | 1) => void;
}

/**
 * Scroll positions that start-align each item, in `scrollLeft` units.
 *
 * Item zero defines where a resting item sits, so its offset is the origin and
 * every other item is measured against it. That keeps the maths independent of
 * where the carousel's padding happens to live, and of any wrapper between the
 * viewport and the items. Bounding rects rather than `offsetLeft`, so the
 * offset parent doesn't matter either.
 */
const itemStarts = (viewport: HTMLElement): number[] => {
  const items = Array.from(viewport.querySelectorAll<HTMLElement>(CAROUSEL_ITEM_SELECTOR));
  if (items.length === 0) return [];

  const originLeft = items[0].getBoundingClientRect().left;
  return items.map((item) => item.getBoundingClientRect().left - originLeft);
};

/**
 * Drives a native horizontal scroller: reports whether it overflows and in
 * which directions it can move, animates paging, and settles onto an item
 * boundary once a drag has come to rest.
 */
export const useCarouselScroll = (): CarouselScroll => {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const animationRef = useRef<{ stop: () => void } | null>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [canScrollBack, setCanScrollBack] = useState(false);
  const [canScrollForward, setCanScrollForward] = useState(false);
  const prefersReducedMotion = useReducedMotion();

  const measure = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;

    const max = el.scrollWidth - el.clientWidth;
    setIsOverflowing(max > 1);
    setCanScrollBack(el.scrollLeft > 1);
    setCanScrollForward(el.scrollLeft < max - 1);
  }, []);

  const stopAnimation = useCallback(() => {
    animationRef.current?.stop();
    animationRef.current = null;
  }, []);

  const animateTo = useCallback(
    (to: number, transition: typeof PAGE_TRANSITION | typeof SETTLE_TRANSITION) => {
      const el = viewportRef.current;
      if (!el) return;

      stopAnimation();
      const max = el.scrollWidth - el.clientWidth;
      const target = Math.max(0, Math.min(to, max));

      if (prefersReducedMotion) {
        el.scrollLeft = target;
        measure();
        return;
      }

      animationRef.current = animate(el.scrollLeft, target, {
        ...transition,
        onUpdate: (value) => {
          el.scrollLeft = Math.max(0, Math.min(value, max));
        },
        onComplete: () => {
          animationRef.current = null;
        },
      });
    },
    [measure, prefersReducedMotion, stopAnimation]
  );

  const scrollByPage = useCallback(
    (direction: -1 | 1) => {
      const el = viewportRef.current;
      if (!el) return;

      stopAnimation();
      const starts = itemStarts(el);
      // A full screenful: items scroll through the bleed rather than being
      // clipped by it, so the whole viewport width is in play.
      const page = el.clientWidth;
      const max = el.scrollWidth - el.clientWidth;

      // Land on the item boundary furthest within one page of travel, so a page
      // never skips content and never stops mid-item.
      if (direction === 1) {
        const reachable = starts.filter(
          (s) => s > el.scrollLeft + 1 && s <= el.scrollLeft + page + 1
        );
        animateTo(reachable.length > 0 ? Math.max(...reachable) : max, PAGE_TRANSITION);
      } else {
        const reachable = starts.filter(
          (s) => s < el.scrollLeft - 1 && s >= el.scrollLeft - page - 1
        );
        animateTo(reachable.length > 0 ? Math.min(...reachable) : 0, PAGE_TRANSITION);
      }
    },
    [animateTo, stopAnimation]
  );

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;

    const observer = new ResizeObserver(measure);
    observer.observe(el);
    const track = el.firstElementChild;
    if (track) observer.observe(track);

    return () => observer.disconnect();
  }, [measure]);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;

    const settle = () => {
      // An animation of our own is already heading for a boundary; the scroll
      // events it emits must not be mistaken for a drag coming to rest.
      if (animationRef.current) return;

      const max = el.scrollWidth - el.clientWidth;
      // At either end the scroller is already where the user put it; correcting
      // there would fight the bounce rather than tidy the position.
      if (el.scrollLeft <= 1 || el.scrollLeft >= max - 1) return;

      const starts = itemStarts(el);
      if (starts.length === 0) return;

      const target = starts.reduce((best, start) =>
        Math.abs(start - el.scrollLeft) < Math.abs(best - el.scrollLeft) ? start : best
      );
      if (Math.abs(target - el.scrollLeft) <= SNAP_THRESHOLD_PX) return;

      animateTo(target, SETTLE_TRANSITION);
    };

    const supportsScrollEnd = 'onscrollend' in el;
    let frame = 0;
    let idleTimer: ReturnType<typeof setTimeout> | undefined;

    const onScroll = () => {
      if (frame === 0) {
        frame = requestAnimationFrame(() => {
          frame = 0;
          measure();
        });
      }
      if (!supportsScrollEnd) {
        clearTimeout(idleTimer);
        idleTimer = setTimeout(settle, SCROLL_IDLE_MS);
      }
    };

    el.addEventListener('scroll', onScroll, { passive: true });
    if (supportsScrollEnd) el.addEventListener('scrollend', settle);
    el.addEventListener('pointerdown', stopAnimation);
    el.addEventListener('wheel', stopAnimation, { passive: true });

    return () => {
      el.removeEventListener('scroll', onScroll);
      if (supportsScrollEnd) el.removeEventListener('scrollend', settle);
      el.removeEventListener('pointerdown', stopAnimation);
      el.removeEventListener('wheel', stopAnimation);
      if (frame !== 0) cancelAnimationFrame(frame);
      clearTimeout(idleTimer);
      stopAnimation();
    };
  }, [animateTo, measure, stopAnimation]);

  return { viewportRef, scrollByPage, isOverflowing, canScrollBack, canScrollForward };
};
