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
export const adjustSelectionInBook = (root: ParentNode, phrase: string) => {
  const chapter = visibleFrame(root)!.contentDocument!;
  select(chapter, rangeOver(chapter, phrase));
};

/** A reader dragging over words in the chapter on screen, and letting go. */
export const selectInBook = (root: ParentNode, phrase: string) => {
  adjustSelectionInBook(root, phrase);
  visibleFrame(root)!.contentDocument!.dispatchEvent(
    new PointerEvent('pointerup', { bubbles: true })
  );
};
