/**
 * A tap told apart from a swipe, across the frames of one book.
 *
 * A page is turned on a phone by dragging the chapter aside, and the finger
 * that did it lifts wherever the new page landed under it — over a highlight as
 * often as not. Both the tap that ends a passage and the tap that opens a
 * highlight ask here first, because neither is what a reader turning pages meant.
 *
 * One watch covers every frame of the book: a gesture can begin in the chapter a
 * page turn leaves behind and end in the one it brings, and the frames are laid
 * over one another, so a point means the same thing in either.
 */

/** How far a finger may travel and still have meant a tap rather than a swipe. */
const TAP_SLOP_PX = 10;

interface Point {
  x: number;
  y: number;
}

/** The gestures made inside the frames of one book, as taps or as swipes. */
export class GestureWatch {
  private pressedAt: Point | null = null;
  private tapped = true;

  /** Follows the pointer through one frame of the book. */
  watch(frame: Window): void {
    // Both in the capture phase, so that whoever acts on a gesture — the selection
    // tracker, or Readium's decorations by way of a message — is answered about the
    // one that is ending rather than the one before it.
    frame.document.addEventListener(
      'pointerdown',
      (event: PointerEvent) => {
        this.pressedAt = { x: event.clientX, y: event.clientY };
        this.tapped = true;
      },
      { capture: true }
    );
    frame.document.addEventListener(
      'pointerup',
      (event: PointerEvent) => {
        this.tapped = this.isNear(event);
      },
      { capture: true }
    );
  }

  /** Whether the gesture ending now, or the one that just ended, was a tap. */
  isTap(): boolean {
    return this.tapped;
  }

  /** A press nobody saw begin is no reason to refuse the reader their tap. */
  private isNear(event: PointerEvent): boolean {
    const pressedAt = this.pressedAt;
    if (!pressedAt) return true;
    return Math.hypot(event.clientX - pressedAt.x, event.clientY - pressedAt.y) <= TAP_SLOP_PX;
  }
}
