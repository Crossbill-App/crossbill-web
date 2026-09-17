/**
 * Everything about selections made inside the book's own chapter frames.
 *
 * It watches each frame for the pointer and `selectionchange` events a passage
 * is made of, and it exists because a browser need not keep showing a passage
 * it is showing: WebKit collapses a selection the engine made itself, so the
 * words the reader still sees are held here rather than left to the frame. It
 * also lets a passage be extended by a tap on a later page — which means
 * swallowing the click that tap would otherwise cause, and keeping a touch
 * gesture over selected words away from the engine's page snapper.
 *
 * It speaks only DOM and the seam's types; which resource a frame is showing is
 * answered by whoever built it.
 */
import type { EbookRect, EbookSelection } from '@/components/reader/engine/EbookReader.ts';
import { listenerSet } from '@/components/reader/engine/listeners.ts';
import {
  caretAt,
  rangeBetween,
  visibleRect,
  type CaretPoint,
} from '@/components/reader/engine/readium/caretRange.ts';
import {
  selectionLocation,
  type EbookResource,
} from '@/components/reader/engine/readium/selectionLocator.ts';
import { debounce } from 'lodash';

/**
 * How long a changing selection is given to settle before it is reported.
 *
 * A drag fires `selectionchange` on every character it crosses, and a touch
 * handle keeps firing it for as long as a finger is on it.
 */
const SELECTION_SETTLE_MS = 200;

/** How far a finger may travel and still have meant a tap rather than a swipe. */
const TAP_SLOP_PX = 10;

/** Which event asked for a report: only the reader's own tap can let a held passage go. */
type ReportSource = 'tap' | 'settled';

/** A passage the engine is holding on to, with the point a further extension runs from. */
interface HeldPassage {
  selection: EbookSelection;
  start: CaretPoint;
}

/** The selections made inside the frames of one book, and the taps that extend them. */
export class SelectionTracker {
  private readonly selectionListeners = listenerSet<EbookSelection | null>();
  private readonly extensionRefusedListeners = listenerSet<void>();
  /** The last selection reported, as its own JSON, so the same one is not reported twice. */
  private reportedSelection: string | null = null;
  /** Where the selection being extended starts; `null` while none is being extended. */
  private extensionAnchor: CaretPoint | null = null;
  /** The passage an extension ended on, kept so that the browser alone cannot take it away. */
  private heldPassage: HeldPassage | null = null;
  private swallowNextClick = false;
  /** Whether a finger or button is still down on the book, mid-selection. */
  private isPressed = false;
  private isDestroyed = false;

  constructor(
    private readonly host: HTMLElement,
    private readonly resourceOf: (frame: Window) => EbookResource | undefined
  ) {}

  /** Takes up everything this tracker listens for in one frame of the book. */
  watch(frame: Window): void {
    this.watchExtension(frame);
    this.watchSelection(frame);
    this.keepTouchFromTheSnapper(frame);
  }

  /** Told from outside when a press ends somewhere the frames cannot hear. */
  pressEnded(): void {
    this.isPressed = false;
  }

  clear(): void {
    for (const frame of this.host.querySelectorAll('iframe')) {
      frame.contentWindow?.getSelection()?.removeAllRanges();
    }
    this.heldPassage = null;
    // Now, not once `selectionchange` settles: the same words selected again
    // before then would be swallowed as a repeat.
    this.reportSelection(null);
  }

  startExtension(): void {
    for (const frame of this.host.querySelectorAll('iframe')) {
      const selection = frame.contentDocument?.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) continue;
      const { startContainer, startOffset } = selection.getRangeAt(0);
      selection.removeAllRanges();
      this.extendFrom({ node: startContainer, offset: startOffset });
      return;
    }
    // A browser showing nothing is not a reader who selected nothing: on iOS the
    // passage being held is the only record of where the words they see start.
    if (this.heldPassage) this.extendFrom(this.heldPassage.start);
  }

  cancelExtension(): void {
    this.extensionAnchor = null;
  }

  onChanged(listener: (selection: EbookSelection | null) => void): () => void {
    return this.selectionListeners.add(listener);
  }

  onExtensionRefused(listener: () => void): () => void {
    return this.extensionRefusedListeners.add(listener);
  }

  destroy(): void {
    this.isDestroyed = true;
    this.extensionAnchor = null;
    this.heldPassage = null;
    this.selectionListeners.clear();
    this.extensionRefusedListeners.clear();
  }

  /** Reports what is selected in one frame of the book, whenever that changes. */
  private watchSelection(frame: Window): void {
    // A mouse is done the moment it is let go, and waiting out the settling
    // delay below to say so would leave the reader looking at selected words
    // and no way to act on them.
    frame.document.addEventListener('pointerdown', () => (this.isPressed = true), {
      capture: true,
    });
    for (const type of ['pointerup', 'pointercancel'] as const) {
      frame.document.addEventListener(type, () => (this.isPressed = false), { capture: true });
    }
    frame.document.addEventListener('pointerup', () => this.reportSelectionIn(frame, 'tap'));
    // Because the pointer going up is not the end of every selection: a touch
    // handle moves the range after it, and a keyboard selection never involves
    // a pointer at all. Not while the finger is still down, though: words offered
    // mid-drag cover the ones the reader is dragging towards.
    frame.document.addEventListener(
      'selectionchange',
      debounce(() => {
        if (!this.isPressed) this.reportSelectionIn(frame, 'settled');
      }, SELECTION_SETTLE_MS)
    );
  }

  /** What one frame of the book has selected, as the resource that frame is showing. */
  private selectionFound(frame: Window): EbookSelection | null {
    const resource = this.resourceOf(frame);
    return resource ? this.selectionIn(frame, resource) : null;
  }

  /** Reports what a frame has selected, which a passage being held outlives. */
  private reportSelectionIn(frame: Window, source: ReportSource): void {
    if (this.isDestroyed) return;
    const found = this.selectionFound(frame);
    // WebKit collapses a selection the engine made itself, which arrives here as
    // nothing being selected: a passage is let go of by a tap, never by the browser.
    if (!found && source === 'settled' && this.heldPassage) {
      this.reportSelection({ ...this.heldPassage.selection, shownAsSelected: false });
      return;
    }
    // A selection found while an extension waits is a swipe's doing, not the reader's:
    // the tap that ends the passage arrives through `watchExtension` instead.
    if (found && this.extensionAnchor) {
      frame.getSelection()?.removeAllRanges();
      return;
    }
    this.heldPassage = null;
    this.reportSelection(found);
  }

  /** Awaits the tap that ends a passage starting here, with nothing selected meanwhile. */
  private extendFrom(start: CaretPoint): void {
    this.extensionAnchor = start;
    this.heldPassage = null;
    // Let go now rather than on `selectionchange`: nothing may hold the reader's
    // gestures back while they are turning pages towards the end of the passage.
    this.reportSelection(null);
  }

  /** Makes the next tap in a frame the far end of the selection being extended. */
  private watchExtension(frame: Window): void {
    // Readium activates a decoration from a pointerup listener on this document, so a
    // tap the extension has taken has to be stopped here, before it travels on.
    const spend = (event: PointerEvent) => {
      this.swallowNextClick = true;
      event.stopPropagation();
    };
    let pressedAt: { x: number; y: number } | null = null;
    const extend = (event: PointerEvent) => {
      const anchor = this.extensionAnchor;
      if (!anchor) return;
      // A finger lifting after a swipe says where the page turn ended, not where the
      // passage does, and a swipe is how the reader reaches the page they want.
      const travelled =
        pressedAt && Math.hypot(event.clientX - pressedAt.x, event.clientY - pressedAt.y);
      if (travelled !== null && travelled > TAP_SLOP_PX) return;
      // Every tap while an extension waits is the extension's, wherever it lands.
      spend(event);
      if (frame.document !== anchor.node.ownerDocument) {
        // The anchor is kept: the reader can turn back to its chapter and tap again.
        this.extensionRefusedListeners.notify(undefined);
        return;
      }
      const caret = caretAt(frame.document, event.clientX, event.clientY);
      const range = caret && rangeBetween(anchor, caret);
      // Extend mode stays on: a tap picking no words is a miss, not a passage.
      if (!range || range.collapsed) return;
      const selection = frame.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
      this.extensionAnchor = null;
      const passage = this.selectionFound(frame);
      // Held, because the words are shown as selected by a browser that need not keep
      // showing them: WebKit collapses a selection nobody dragged.
      this.heldPassage = passage && {
        selection: passage,
        start: { node: range.startContainer, offset: range.startOffset },
      };
      this.reportSelection(passage);
    };
    const swallow = (event: MouseEvent) => {
      if (!this.swallowNextClick) return;
      this.swallowNextClick = false;
      // That tap is spent on the extension: it must not also follow a link in the
      // book or reach anything else of the book's own that listens for a click.
      event.stopPropagation();
      event.preventDefault();
    };
    frame.document.addEventListener('pointerup', extend, { capture: true });
    frame.document.addEventListener('click', swallow, { capture: true });
    // A gesture beginning says the last one's click is never coming, and a swallow
    // left standing would eat this one instead.
    frame.document.addEventListener(
      'pointerdown',
      (event: PointerEvent) => {
        this.swallowNextClick = false;
        pressedAt = { x: event.clientX, y: event.clientY };
      },
      { capture: true }
    );
  }

  /** Keeps a touch gesture over selected words away from Readium's snapper. */
  private keepTouchFromTheSnapper(frame: Window): void {
    // The snapper listens on the frame's window in the bubble phase, so the document
    // hears first: its first move deselects, and its end reports a swipe.
    const holdsWords = () => {
      const selection = frame.getSelection();
      return !!selection && selection.rangeCount > 0 && !selection.isCollapsed;
    };
    let letThrough = false;
    const holdBack = (event: TouchEvent) => {
      // An extension waiting is the reader turning pages towards the end of the passage,
      // so nothing is held back: the selection a swipe leaves is dropped when reported.
      const hold = !this.extensionAnchor && holdsWords();
      // The snapper runs a state machine over the three events: one it has already begun
      // is stranded part-turned unless it hears an end.
      if (hold && letThrough) frame.dispatchEvent(new TouchEvent('touchend'));
      // Never `preventDefault`: the browser's own selection handles ride on the default.
      if (hold) event.stopPropagation();
      letThrough = !hold && event.type !== 'touchend' && event.type !== 'touchcancel';
    };
    for (const type of ['touchstart', 'touchmove', 'touchend', 'touchcancel'] as const) {
      frame.document.addEventListener(type, holdBack, { capture: true });
    }
  }

  /**
   * One report per passage.
   *
   * The two events above overlap by design — a mouse drag settles under both —
   * and every tap in the book ends with nothing selected, which is not news to
   * a reader who had selected nothing. Keyed on the location and on whether the
   * browser is showing it: a reflow that moves the same words is not a new
   * selection, while the browser dropping them is news the UI has to act on.
   */
  private reportSelection(selection: EbookSelection | null): void {
    const key = selection && JSON.stringify([selection.location, selection.shownAsSelected]);
    if (key === this.reportedSelection) return;
    this.reportedSelection = key;
    this.selectionListeners.notify(selection);
  }

  private selectionIn(frame: Window, resource: EbookResource): EbookSelection | null {
    const selected = frame.getSelection();
    if (!selected || selected.rangeCount === 0) return null;
    const range = selected.getRangeAt(0);
    const location = selectionLocation(range, resource);
    return location && { location, rect: this.onScreen(frame, range), shownAsSelected: true };
  }

  /** A range inside a frame, in the coordinates of the page the reader is on. */
  private onScreen(frame: Window, range: Range): EbookRect {
    const rect = visibleRect(frame, range);
    const origin = [...this.host.querySelectorAll('iframe')]
      .find((candidate) => candidate.contentWindow === frame)
      ?.getBoundingClientRect();
    return {
      x: rect.x + (origin?.x ?? 0),
      y: rect.y + (origin?.y ?? 0),
      width: rect.width,
      height: rect.height,
    };
  }
}
