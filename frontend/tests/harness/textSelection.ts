/** Dragging over words in a loaded document, which is how a reader starts a highlight. */

/** The `occurrence`th text node holding `phrase`, and where in it the phrase starts. */
const findText = (doc: Document, phrase: string, occurrence: number) => {
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
  let seen = 0;
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    const index = node.data.indexOf(phrase);
    if (index === -1) continue;
    seen += 1;
    if (seen === occurrence) return { node, index };
  }
  throw new Error(`The document has no occurrence ${occurrence} of "${phrase}".`);
};

/** What a reader dragging over `phrase` leaves selected. */
export const rangeOver = (doc: Document, phrase: string, occurrence = 1): Range => {
  const { node, index } = findText(doc, phrase, occurrence);
  const range = doc.createRange();
  range.setStart(node, index);
  range.setEnd(node, index + phrase.length);
  return range;
};

/** A drag that starts at one phrase and ends at another, elsewhere in the document. */
export const rangeFromTo = (doc: Document, from: string, to: string): Range => {
  const start = findText(doc, from, 1);
  const end = findText(doc, to, 1);
  const range = doc.createRange();
  range.setStart(start.node, start.index);
  range.setEnd(end.node, end.index + to.length);
  return range;
};

/** Leaves `range` selected in the window the document belongs to. */
const select = (doc: Document, range: Range): void => {
  const selection = doc.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
};

/** The chapter on screen under `root`: Readium keeps the neighbouring one loaded and hidden. */
export const visibleFrame = (root: ParentNode) =>
  [...root.querySelectorAll('iframe')].find((candidate) => candidate.style.visibility !== 'hidden');

/** A selection changing under no pointer, the way a touch handle or a keyboard moves one. */
export const adjustSelectionInBook = (root: ParentNode, phrase: string, occurrence = 1) => {
  const chapter = visibleFrame(root)!.contentDocument!;
  select(chapter, rangeOver(chapter, phrase, occurrence));
};

/** A tap in a chapter, at a point in that chapter's own coordinates. */
export const tapAt = (chapter: Document, point: { x: number; y: number }) =>
  // On the element under the point, as a real tap lands: a listener on the document
  // that stops the event then keeps it from the rest of the document, as it would.
  (chapter.elementFromPoint(point.x, point.y) ?? chapter).dispatchEvent(
    new PointerEvent('pointerup', { bubbles: true, clientX: point.x, clientY: point.y })
  );

/** Where a reader would tap to put the caret before a range's first character. */
export const startOf = (range: Range) => {
  const rect = range.getClientRects()[0];
  return { x: rect.left + 1, y: rect.top + rect.height / 2 };
};

/** Where a reader would tap to put the caret after a range's last character. */
export const endOf = (range: Range) => {
  const rects = range.getClientRects();
  const rect = rects[rects.length - 1];
  return { x: rect.right - 1, y: rect.top + rect.height / 2 };
};

/**
 * Which of the chapter's identical paragraphs are on the page, by their number.
 *
 * Each paragraph holds the chapter's sentence once, so a paragraph's number is
 * also which occurrence of any of its words `rangeOver` should be asked for.
 */
export const paragraphsOnThePage = (chapter: Document): number[] => {
  const view = chapter.defaultView!;
  return [...chapter.querySelectorAll('p')].flatMap((paragraph, index) => {
    const rect = paragraph.getBoundingClientRect();
    const onThePage =
      rect.left >= 0 &&
      rect.right <= view.innerWidth &&
      rect.top >= 0 &&
      rect.bottom <= view.innerHeight;
    return onThePage ? [index + 1] : [];
  });
};

/** A reader dragging over words in the chapter on screen, and letting go. */
export const selectInBook = (root: ParentNode, phrase: string, occurrence = 1) => {
  adjustSelectionInBook(root, phrase, occurrence);
  visibleFrame(root)!.contentDocument!.dispatchEvent(
    new PointerEvent('pointerup', { bubbles: true })
  );
};
