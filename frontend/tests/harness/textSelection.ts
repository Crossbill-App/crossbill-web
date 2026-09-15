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
export const select = (doc: Document, range: Range): void => {
  const selection = doc.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
};
