import type { EbookScreen } from '@/components/reader/engine/EbookReader.ts';
import {
  caretAt,
  isOnScreen,
  wordEdgeAt,
  type CaretPoint,
} from '@/components/reader/engine/readium/caretRange.ts';
import {
  selectionLocation,
  type EbookResource,
} from '@/components/reader/engine/readium/selectionLocator.ts';

/** Forwards through the document, or backwards. */
type Direction = 1 | -1;

interface Character {
  node: Text;
  index: number;
}

/** Laid out on the screen, laid out elsewhere (another page), or not laid out at all. */
type Placement = 'on' | 'off' | 'unplaced';

// Enough to tell one passage from another without quoting a whole sentence.
const QUOTE_LETTERS = 30;

// Fractions of the frame, from the corner inwards: a point in a margin can resolve
// to text on another page, so one point is not enough.
const PROBE_ROWS = [0.02, 0.06, 0.12, 0.25, 0.4];
const PROBE_COLUMNS = [0.04, 0.15];

const isText = (node: Node): node is Text => node.nodeType === Node.TEXT_NODE;

/** The characters at and after `offset`, or the ones before it, across text nodes. */
function* charactersFrom(node: Text, offset: number, direction: Direction): Generator<Character> {
  const document = node.ownerDocument;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  walker.currentNode = node;
  let current: Text | null = node;
  let index = direction > 0 ? offset : offset - 1;
  while (current) {
    for (; index >= 0 && index < current.length; index += direction) {
      yield { node: current, index };
    }
    current = (direction > 0 ? walker.nextNode() : walker.previousNode()) as Text | null;
    index = direction > 0 ? 0 : (current?.length ?? 0) - 1;
  }
}

const placementOf = (frame: Window, { node, index }: Character): Placement => {
  const range = node.ownerDocument.createRange();
  range.setStart(node, index);
  range.setEnd(node, index + 1);
  const rects = [...range.getClientRects()].filter((rect) => rect.width > 0 && rect.height > 0);
  if (rects.length === 0) return 'unplaced';
  return rects.some((rect) => isOnScreen(frame, rect)) ? 'on' : 'off';
};

/** The first laid-out character from a caret, if it is on screen. */
const nearestOnScreen = (frame: Window, caret: CaretPoint, direction: Direction) => {
  if (!isText(caret.node)) return null;
  for (const character of charactersFrom(caret.node, caret.offset, direction)) {
    const placement = placementOf(frame, character);
    if (placement !== 'unplaced') return placement === 'on' ? character : null;
  }
  return null;
};

/** The last character on screen before the text, read in `direction`, leaves it. */
const furthestOnScreen = (frame: Window, seed: Character, direction: Direction): Character => {
  let furthest = seed;
  const after = direction > 0 ? seed.index + 1 : seed.index;
  for (const character of charactersFrom(seed.node, after, direction)) {
    const placement = placementOf(frame, character);
    if (placement === 'off') break;
    if (placement === 'on') furthest = character;
  }
  return furthest;
};

const probePoints = (frame: Window, inward: Direction) =>
  PROBE_ROWS.flatMap((row) =>
    PROBE_COLUMNS.map((column) =>
      inward > 0
        ? { x: column * frame.innerWidth, y: row * frame.innerHeight }
        : { x: (1 - column) * frame.innerWidth, y: (1 - row) * frame.innerHeight }
    )
  );

/** The first character on screen (`inward` 1, probed from the top left) or the last (-1). */
const screenEdge = (frame: Window, inward: Direction): Character | null => {
  for (const point of probePoints(frame, inward)) {
    const caret = caretAt(frame.document, point.x, point.y);
    const seed = caret && nearestOnScreen(frame, caret, inward);
    if (seed) return furthestOnScreen(frame, seed, -inward as Direction);
  }
  return null;
};

/** Where a quote of the few words from `node`/`offset` in `direction` ends, on a word's edge. */
const quoteEnd = (node: Text, offset: number, direction: Direction): CaretPoint => {
  let counted = 0;
  let reached: CaretPoint = { node, offset };
  for (const character of charactersFrom(node, offset, direction)) {
    reached = { node: character.node, offset: character.index + (direction > 0 ? 1 : 0) };
    if (/\S/.test(character.node.data[character.index])) counted += 1;
    if (counted >= QUOTE_LETTERS) break;
  }
  return wordEdgeAt(reached, direction);
};

const rangeOf = (start: CaretPoint, end: CaretPoint): Range => {
  const range = start.node.ownerDocument!.createRange();
  range.setStart(start.node, start.offset);
  range.setEnd(end.node, end.offset);
  return range;
};

/** The text a screen of this frame starts and ends with, or `null` where it shows none. */
export const screenIn = (frame: Window, resource: EbookResource): EbookScreen | null => {
  const foundFirst = screenEdge(frame, 1);
  const foundLast = screenEdge(frame, -1);
  const first = foundFirst ?? (foundLast && furthestOnScreen(frame, foundLast, -1));
  const last = foundLast ?? (foundFirst && furthestOnScreen(frame, foundFirst, 1));
  if (!first || !last) return null;

  const startPoint = { node: first.node, offset: first.index };
  const endPoint = { node: last.node, offset: last.index + 1 };
  const start = selectionLocation(
    rangeOf(startPoint, quoteEnd(first.node, first.index, 1)),
    resource
  );
  const end = selectionLocation(
    rangeOf(quoteEnd(last.node, last.index + 1, -1), endPoint),
    resource
  );
  return start && end ? { start, end } : null;
};
