import {
  isInsideWord,
  rangeBetween,
  visibleRect,
  wordEdgeAt,
} from '@/components/reader/caretRange.ts';
import { expect, test } from 'vitest';

const SENTENCE = 'Attention, please. Read on.';

/** The paragraph's one text node, which is what a caret in a chapter resolves to. */
const words = (): Text => {
  const paragraph = document.createElement('p');
  paragraph.textContent = SENTENCE;
  return paragraph.firstChild as Text;
};

test('a boundary inside a word is pushed out to the edge of that word', () => {
  const node = words();

  // Between the "e" and the "n" of "Attention".
  expect(wordEdgeAt({ node, offset: 4 }, -1).offset).toBe(0);
  expect(wordEdgeAt({ node, offset: 4 }, 1).offset).toBe(9);
});

test('a boundary already in the whitespace between words stays where it is', () => {
  const node = words();

  expect(wordEdgeAt({ node, offset: 10 }, -1).offset).toBe(10);
  expect(wordEdgeAt({ node, offset: 10 }, 1).offset).toBe(10);
});

test('a caret before the anchor still gives a forward range of whole words', () => {
  const node = words();

  // Tapped inside "please" first, then dragged back into "Attention".
  const range = rangeBetween({ node, offset: 14 }, { node, offset: 4 });

  expect(range?.toString()).toBe('Attention, please');
});

test('a boundary against the punctuation stuck to a word is not inside it', () => {
  expect(isInsideWord(SENTENCE, 9)).toBe(false);
  expect(isInsideWord(SENTENCE, 4)).toBe(true);
});

test('a range with no rectangle on screen falls back to the box around all of them', () => {
  const paragraph = document.createElement('p');
  paragraph.textContent = SENTENCE;
  paragraph.style.position = 'absolute';
  paragraph.style.left = '-9999px';
  document.body.append(paragraph);
  const range = document.createRange();
  range.selectNodeContents(paragraph);

  const rect = visibleRect(window, range);

  expect(rect.left).toBe(range.getBoundingClientRect().left);
  expect(rect.width).toBe(range.getBoundingClientRect().width);
  paragraph.remove();
});
