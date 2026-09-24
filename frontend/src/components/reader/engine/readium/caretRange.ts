/** A place in a chapter, as a tap or a selection boundary names one. */
export interface CaretPoint {
  node: Node;
  offset: number;
}

// Optional because a browser has one of the two: `caretPositionFromPoint` is the
// standard, and WebKit still ships only the older `caretRangeFromPoint`.
type CaretFinder = Partial<Pick<Document, 'caretPositionFromPoint' | 'caretRangeFromPoint'>>;

/** Where in a document a point on screen lands, or `null` where nothing does. */
export const caretAt = (document: CaretFinder, x: number, y: number): CaretPoint | null => {
  const position = document.caretPositionFromPoint?.(x, y);
  if (position) return { node: position.offsetNode, offset: position.offset };
  const range = document.caretRangeFromPoint?.(x, y);
  return range ? { node: range.startContainer, offset: range.startOffset } : null;
};

// Letters and digits alone, so a word ends before the punctuation stuck to it: a rule
// this small is worth more here than a segmenter, which no two engines agree on.
const WORD_CHARACTER = /[\p{L}\p{N}]/u;

/** Whether a boundary has word on both sides of it, which is where a tap lands inside one. */
const isInsideWord = (text: string, offset: number): boolean =>
  WORD_CHARACTER.test(text[offset - 1] ?? '') && WORD_CHARACTER.test(text[offset] ?? '');

/**
 * A boundary a tap left inside a word, moved out to that word's edge.
 *
 * `step` is -1 for a range's start and 1 for its end; a boundary already on an edge,
 * or in anything but text, stays where it is rather than being guessed at.
 */
export const wordEdgeAt = (point: CaretPoint, step: -1 | 1): CaretPoint => {
  const text = point.node.nodeType === Node.TEXT_NODE ? (point.node as Text).data : null;
  if (text === null || !isInsideWord(text, point.offset)) return point;
  let offset = point.offset;
  // Backwards reads the character before the boundary, forwards the one at it.
  while (WORD_CHARACTER.test(text[step < 0 ? offset - 1 : offset] ?? '')) offset += step;
  return { node: point.node, offset };
};

/** The anchor and a caret as one range, running forwards whichever of them the reader tapped. */
export const rangeBetween = (anchor: CaretPoint, caret: CaretPoint): Range | null => {
  const chapter = anchor.node.ownerDocument;
  if (!chapter) return null;
  const range = chapter.createRange();
  range.setStart(anchor.node, anchor.offset);
  if (range.comparePoint(caret.node, caret.offset) < 0) range.setStart(caret.node, caret.offset);
  else range.setEnd(caret.node, caret.offset);
  // Both ends, because a tap resolves to a character position and either end of the
  // range may be the one it set.
  const start = wordEdgeAt({ node: range.startContainer, offset: range.startOffset }, -1);
  const end = wordEdgeAt({ node: range.endContainer, offset: range.endOffset }, 1);
  range.setStart(start.node, start.offset);
  range.setEnd(end.node, end.offset);
  return range;
};

const isOnScreen = (frame: Window, rect: DOMRect): boolean =>
  rect.right > 0 && rect.left < frame.innerWidth && rect.bottom > 0 && rect.top < frame.innerHeight;

/** A page is a column, so the bounding box of a range spanning several of them covers
 * every page it crosses, and anything placed beside that box misses the page on screen. */
export const visibleRect = (frame: Window, range: Range): DOMRect => {
  const rects = [...range.getClientRects()].filter((rect) => isOnScreen(frame, rect));
  if (rects.length === 0) return range.getBoundingClientRect();
  const left = Math.min(...rects.map((rect) => rect.left));
  const top = Math.min(...rects.map((rect) => rect.top));
  const right = Math.max(...rects.map((rect) => rect.right));
  const bottom = Math.max(...rects.map((rect) => rect.bottom));
  return new DOMRect(left, top, right - left, bottom - top);
};
