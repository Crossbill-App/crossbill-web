import { useCallback, useEffect, useRef } from 'react';

/** How much of each edge of the reading surface turns a page. */
const TAP_ZONE_FRACTION = 0.2;

/**
 * How far a pointer may travel and still be a tap.
 *
 * A swipe, a drag across text and a flick to scroll all begin as a pointerdown
 * on the page; the distance travelled is what separates them from a finger put
 * down and lifted in one place. Generous enough to forgive the wobble a thumb
 * puts into a deliberate tap.
 */
const TAP_SLOP_PX = 10;

/**
 * How long a pointer may be held and still be a tap.
 *
 * A long press is the gesture that opens a selection, and it must not also cost
 * the reader their page.
 */
const TAP_MAX_MS = 500;

/** Things that answer a pointer themselves, and whose answer is not a page turn. */
const INTERACTIVE_SELECTOR =
  'a[href], button, input, select, textarea, summary, [role="button"], [role="link"]';

interface TapOrigin {
  x: number;
  y: number;
  at: number;
  /** Whether text was already selected when the pointer went down. */
  overSelection: boolean;
}

/**
 * The interactive element a pointer landed on, if any.
 *
 * `instanceof Element` is no use here: the target belongs to the publication's
 * own document, a separate realm whose `Element` is not this one — the same
 * property the reader's key handler relies on to ignore in-frame events.
 */
const nearestInteractive = (target: EventTarget | null): Element | null => {
  const element = target as Element | null;
  return typeof element?.closest === 'function' ? element.closest(INTERACTIVE_SELECTOR) : null;
};

interface ReaderTapZoneOptions {
  /** False wherever the arrow buttons are shown, which is where taps are not wanted. */
  enabled: boolean;
  /** Page turns are held while true, as they are for the arrow buttons. */
  suspended: boolean;
  onPrevious: () => void;
  onNext: () => void;
}

/**
 * Turning pages by tapping the edges of the book.
 *
 * Returns a function to give each publication frame as it loads. The listeners
 * go *inside* the frame rather than over it: an overlay across the reading
 * surface would be the simpler thing to write, but it would sit between the
 * reader and the book and eat the selection, the links and the scrolling that
 * belong to the publication's own document. A same-origin frame does not bubble
 * its events out, so reaching into it through `frameLoaded` is the same seam the
 * arrow keys already use.
 *
 * Readium has a tap pager of its own — fixed quarters, no notion of how long the
 * pointer was down — which the reader suppresses by returning `true` from the
 * navigator's `tap` and `click` listeners. That must stay true, or a tap here
 * would turn two pages.
 */
export const useReaderTapZones = ({
  enabled,
  suspended,
  onPrevious,
  onNext,
}: ReaderTapZoneOptions) => {
  // Mirrored into a ref rather than closed over, so that crossing the breakpoint
  // or renewing a session does not change the identity of the binder below —
  // which is a dependency of the boot effect, and so would rebuild the navigator.
  const gateRef = useRef({ enabled, suspended });
  useEffect(() => {
    gateRef.current = { enabled, suspended };
  }, [enabled, suspended]);

  // `frameLoaded` fires again for a frame the pool has kept, and these listeners
  // are fresh closures every time, so `addEventListener` would not dedupe them.
  const boundFrames = useRef(new WeakSet<Window>());

  return useCallback(
    (frameWindow: Window) => {
      if (boundFrames.current.has(frameWindow)) return;
      boundFrames.current.add(frameWindow);

      const isSelecting = () => frameWindow.getSelection()?.isCollapsed === false;

      let origin: TapOrigin | null = null;

      frameWindow.addEventListener('pointerdown', (event) => {
        origin = event.isPrimary
          ? {
              x: event.clientX,
              y: event.clientY,
              at: Date.now(),
              overSelection: isSelecting(),
            }
          : null;
      });

      // A gesture the browser took over — a scroll, or a system gesture from the
      // edge of the screen — never becomes a tap.
      frameWindow.addEventListener('pointercancel', () => {
        origin = null;
      });

      frameWindow.addEventListener('pointerup', (event) => {
        const start = origin;
        origin = null;
        const { enabled: tapsTurnPages, suspended: held } = gateRef.current;
        if (!start || !tapsTurnPages || held) return;

        if (
          Math.abs(event.clientX - start.x) > TAP_SLOP_PX ||
          Math.abs(event.clientY - start.y) > TAP_SLOP_PX
        )
          return;
        if (Date.now() - start.at > TAP_MAX_MS) return;

        // A tap on a selection, or the one that dismisses it. The second is why
        // the pointer's *origin* is consulted as well: by the time the pointer
        // comes up the browser has already collapsed what was selected, so the
        // tap that ended a selection would otherwise read as an ordinary one.
        if (start.overSelection || isSelecting()) return;

        if (nearestInteractive(event.target)) return;

        const zone = frameWindow.innerWidth * TAP_ZONE_FRACTION;
        if (event.clientX < zone) onPrevious();
        else if (event.clientX > frameWindow.innerWidth - zone) onNext();
      });
    },
    [onPrevious, onNext]
  );
};
