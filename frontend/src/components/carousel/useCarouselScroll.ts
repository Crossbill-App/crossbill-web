import { animate, useReducedMotion } from 'motion/react';
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

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

interface Metrics {
  isOverflowing: boolean;
  canScrollBack: boolean;
  canScrollForward: boolean;
}

const INITIAL_METRICS: Metrics = {
  isOverflowing: false,
  canScrollBack: false,
  canScrollForward: false,
};

/**
 * Scroll positions that start-align each item, in `scrollLeft` units.
 *
 * Measured from bounding rects rather than `offsetLeft` so the numbers stay
 * correct regardless of which ancestor happens to be the offset parent.
 */
const itemStarts = (viewport: HTMLElement): number[] => {
  const viewportLeft = viewport.getBoundingClientRect().left;
  return Array.from(viewport.querySelectorAll<HTMLElement>('[data-carousel-item]')).map(
    (item) => viewport.scrollLeft + item.getBoundingClientRect().left - viewportLeft
  );
};

const nearestStart = (starts: number[], scrollLeft: number): number | null =>
  starts.reduce<number | null>(
    (best, start) =>
      best === null || Math.abs(start - scrollLeft) < Math.abs(best - scrollLeft) ? start : best,
    null
  );

/**
 * Drives a native horizontal scroller: reports whether it overflows and in
 * which directions it can move, animates paging, and settles onto an item
 * boundary once a drag has come to rest.
 */
export const useCarouselScroll = (): CarouselScroll => {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const animationRef = useRef<{ stop: () => void } | null>(null);
  const isAnimatingRef = useRef(false);
  const [metrics, setMetrics] = useState<Metrics>(INITIAL_METRICS);
  const prefersReducedMotion = useReducedMotion();

  const measure = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;

    const max = el.scrollWidth - el.clientWidth;
    const next: Metrics = {
      isOverflowing: max > 1,
      canScrollBack: el.scrollLeft > 1,
      canScrollForward: el.scrollLeft < max - 1,
    };
    setMetrics((prev) =>
      prev.isOverflowing === next.isOverflowing &&
      prev.canScrollBack === next.canScrollBack &&
      prev.canScrollForward === next.canScrollForward
        ? prev
        : next
    );
  }, []);

  const stopAnimation = useCallback(() => {
    animationRef.current?.stop();
    animationRef.current = null;
    isAnimatingRef.current = false;
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

      // The flag keeps the settle detector from reacting to the scroll events
      // this animation itself emits.
      isAnimatingRef.current = true;
      animationRef.current = animate(el.scrollLeft, target, {
        ...transition,
        onUpdate: (value) => {
          el.scrollLeft = Math.max(0, Math.min(value, max));
        },
        onComplete: () => {
          isAnimatingRef.current = false;
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
      if (isAnimatingRef.current) return;

      const max = el.scrollWidth - el.clientWidth;
      // At either end the scroller is already where the user put it; correcting
      // there would fight the bounce rather than tidy the position.
      if (el.scrollLeft <= 1 || el.scrollLeft >= max - 1) return;

      const target = nearestStart(itemStarts(el), el.scrollLeft);
      if (target === null || Math.abs(target - el.scrollLeft) <= SNAP_THRESHOLD_PX) return;

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

  return { viewportRef, scrollByPage, ...metrics };
};
