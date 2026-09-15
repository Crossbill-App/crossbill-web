/**
 * What a browser selection is, said in the terms another client can find again.
 *
 * A `Range` is a pair of nodes and offsets in one loaded document, which means
 * nothing to the backend or to KOReader. What both can use is the Readium
 * locator the rest of the reader already speaks: the resource, a selector for
 * the element holding the words, the words themselves, and enough text either
 * side to tell this occurrence of them from the book's other ones.
 *
 * Whitespace is collapsed on the way out. A chapter's source carries the
 * indentation of its markup between elements, and none of that is text anyone
 * reading the book can see, so collapsing keeps the context's few characters
 * for words. `xpoint-cfi` collapses both sides of its own comparison, and
 * resolves a quote whether or not a break between blocks reads as a space;
 * ADR-0004 *Amendment 8* records the check.
 */
import type { EbookLocation } from '@/components/reader/EbookReader.ts';

/**
 * How much text either side of the quote is kept.
 *
 * Enough to separate repeated wording — a phrase a book uses in two chapters,
 * or a paragraph it repeats — without quoting the neighbours at length.
 */
const CONTEXT_CHARS = 40;

/** An id safe to write into a selector as it stands. */
const PLAIN_ID = /^[A-Za-z][A-Za-z0-9_-]*$/;

/** Which resource of the publication a selection was made in. */
export interface EbookResource {
  href: string;
  type: string;
}

/** U+FEFF is whitespace to `\s`, but a character `xpoint-cfi` deletes rather than reads as a space. */
const collapse = (text: string): string => text.replace(/\uFEFF/g, '').replace(/\s+/g, ' ');

const indexIn = (parent: Element, child: Element): number =>
  [...parent.children].indexOf(child) + 1;

/**
 * The element's id, where it is one selector syntax and this document agree on.
 *
 * An id needing escaping is passed over rather than escaped: the `:nth-child`
 * path below always works, while an id written wrong names another element, and
 * a selector that resolves to the wrong paragraph is worse than a longer one. A
 * document with the same id twice is the same hazard by another route.
 */
const plainIdOf = (element: Element): string | null => {
  const id = element.id;
  if (!id || !PLAIN_ID.test(id)) return null;
  return element.ownerDocument.getElementById(id) === element ? id : null;
};

/**
 * A `querySelector`-resolvable path to one element, nearest step last.
 *
 * Deliberately the narrow dialect the derived locators already use — an id or
 * `body` at the root and `tag:nth-child(n)` for every step below it — rather
 * than the wider one Readium's own injected generator emits. Both ends of the
 * round trip have to agree on a selector: the backend resolves these against a
 * parsed EPUB rather than with `querySelector`, and this is the shape its
 * resolver is exercised with. ADR-0004 *Amendment 8* has the reasoning.
 */
const selectorSteps = (element: Element): string[] => {
  const id = plainIdOf(element);
  if (id) return [`#${id}`];
  if (element === element.ownerDocument.body) return ['body'];
  const parent = element.parentElement;
  if (!parent) return [element.localName];
  return [...selectorSteps(parent), `${element.localName}:nth-child(${indexIn(parent, element)})`];
};

/** The element the selection lies in: its common ancestor, or the one holding its text. */
const containerOf = (range: Range): Element | null => {
  const node = range.commonAncestorContainer;
  return node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
};

/** Everything in the resource before the selection, and everything after it. */
const surroundings = (range: Range, body: HTMLElement): [string, string] => {
  const before = range.cloneRange();
  before.selectNodeContents(body);
  before.setEnd(range.startContainer, range.startOffset);
  const after = range.cloneRange();
  after.selectNodeContents(body);
  after.setStart(range.endContainer, range.endOffset);
  return [before.toString(), after.toString()];
};

/**
 * Where in the book a selection is, or `null` when it selects no words at all.
 *
 * Whitespace the reader dragged over at either end of the quote is handed to
 * the context it borders rather than dropped, so that `before` and `after`
 * still meet the quote: text abutting it on both sides is what tells the
 * backend it found the passage rather than something that reads like it.
 */
export const selectionLocation = (range: Range, resource: EbookResource): EbookLocation | null => {
  const body = range.startContainer.ownerDocument?.body;
  const container = containerOf(range);
  if (!body || !container) return null;

  const selected = range.toString();
  const quote = selected.trim();
  // A caret, or a drag that landed on the space between two words.
  if (!quote) return null;
  const leading = selected.slice(0, selected.length - selected.trimStart().length);
  const trailing = selected.slice(selected.trimEnd().length);
  const [before, after] = surroundings(range, body);

  return {
    href: resource.href,
    type: resource.type,
    locations: { cssSelector: selectorSteps(container).join(' > ') },
    text: {
      // Trimmed at the far edge only: the indentation the resource opens and
      // closes with is markup rather than anything a reader sees, while the
      // space bordering the quote is what makes the context abut it.
      before: collapse(before + leading)
        .trimStart()
        .slice(-CONTEXT_CHARS),
      highlight: collapse(quote),
      after: collapse(trailing + after)
        .trimEnd()
        .slice(0, CONTEXT_CHARS),
    },
  };
};
