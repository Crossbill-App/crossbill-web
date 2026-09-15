import { selectionLocation, type EbookResource } from '@/components/reader/selectionLocator.ts';
import { rangeFromTo, rangeOver } from '@tests/harness/textSelection';
import { expect, test } from 'vitest';

/** A chapter as an EPUB ships one: XHTML, indented, some of it under an id. */
const A_CHAPTER = `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>On Attention</title></head>
  <body>
    <h1>On Attention</h1>
    <section id="first">
      <p>Attention is the rarest and purest form of generosity.</p>
      <p>The same words, <em>emphasised</em>, and then some more of them.</p>
    </section>
    <section>
      <p>Attention is the rarest and purest form of generosity.</p>
    </section>
  </body>
</html>`;

const CHAPTER: EbookResource = {
  href: 'resources/OEBPS/chapter1.xhtml',
  type: 'application/xhtml+xml',
};

const chapter = () => new DOMParser().parseFromString(A_CHAPTER, 'application/xhtml+xml');

test('a selection is the words, the element holding them, and the text either side', () => {
  const doc = chapter();

  const location = selectionLocation(rangeOver(doc, 'rarest and purest'), CHAPTER);

  expect(location?.href).toBe('resources/OEBPS/chapter1.xhtml');
  expect(location?.type).toBe('application/xhtml+xml');
  expect(location?.locations.cssSelector).toBe('#first > p:nth-child(1)');
  expect(location?.text?.highlight).toBe('rarest and purest');
  expect(location?.text?.before).toBe('On Attention Attention is the ');
  expect(location?.text?.after).toBe(' form of generosity. The same words, emp');
});

test('the selector reaches the element the words are actually in', () => {
  const doc = chapter();

  const first = selectionLocation(rangeOver(doc, 'rarest and purest', 1), CHAPTER);
  const second = selectionLocation(rangeOver(doc, 'rarest and purest', 2), CHAPTER);

  // The same words twice in the chapter, told apart by where they are.
  expect(second?.locations.cssSelector).toBe('body > section:nth-child(3) > p:nth-child(1)');
  const found = doc.querySelector(second?.locations.cssSelector ?? '');
  expect(found).not.toBeNull();
  expect(found).not.toBe(doc.querySelector(first?.locations.cssSelector ?? ''));
  expect(found?.textContent).toContain('rarest and purest');
});

test('the text either side is bounded, and carries none of the markup indentation', () => {
  const doc = chapter();

  const location = selectionLocation(rangeOver(doc, 'rarest and purest', 2), CHAPTER);

  expect(location?.text?.before).toHaveLength(40);
  expect(location?.text?.before?.endsWith('Attention is the ')).toBe(true);
  // What is left of the chapter after the second occurrence is shorter than the bound.
  expect(location?.text?.after).toBe(' form of generosity.');
  expect(location?.text?.before).not.toMatch(/\s\s|\n/);
});

test('a selection inside an inline element names that element', () => {
  const doc = chapter();

  const location = selectionLocation(rangeOver(doc, 'emphasised'), CHAPTER);

  expect(location?.locations.cssSelector).toBe('#first > p:nth-child(2) > em:nth-child(1)');
});

test('a selection across two paragraphs names what holds them both', () => {
  const doc = chapter();

  const location = selectionLocation(rangeFromTo(doc, 'purest form', 'The same words'), CHAPTER);

  expect(location?.locations.cssSelector).toBe('#first');
  expect(location?.text?.highlight).toBe('purest form of generosity. The same words');
});

test('whitespace the reader dragged over joins the context rather than the quote', () => {
  const doc = chapter();

  const location = selectionLocation(rangeOver(doc, ' rarest and purest '), CHAPTER);

  expect(location?.text?.highlight).toBe('rarest and purest');
  // Still abutting the quote, which is what tells a match from a lookalike.
  expect(location?.text?.before).toBe('On Attention Attention is the ');
  expect(location?.text?.after).toBe(' form of generosity. The same words, emp');
});

test('a caret, and a drag that landed between two words, select nothing', () => {
  const doc = chapter();
  const caret = rangeOver(doc, 'rarest');
  caret.collapse(true);

  expect(selectionLocation(caret, CHAPTER)).toBeNull();
  expect(selectionLocation(rangeOver(doc, ' '), CHAPTER)).toBeNull();
});
