import type { EbookTocEntry } from '@/components/reader/engine/EbookReader.ts';
import {
  chapterProgressAt,
  chapterStartsIn,
  sectionIdsIn,
} from '@/components/reader/engine/readium/chapterProgress.ts';
import { Locator } from '@readium/shared';
import { expect, test } from 'vitest';

const COVER = 'resources/OEBPS/cover.xhtml';
const CHAPTER_ONE = 'resources/OEBPS/chapter1.xhtml';
const CHAPTER_ONE_CONTINUED = 'resources/OEBPS/chapter1b.xhtml';
const CHAPTER_TWO = 'resources/OEBPS/chapter2.xhtml';

const at = (href: string, position: number): Locator =>
  new Locator({ href, type: 'application/xhtml+xml' }).copyWithLocations({ position });

const entry = (href: string, children: EbookTocEntry[] = []): EbookTocEntry => ({
  href,
  type: '',
  title: href,
  children,
});

/** A cover the contents skip, a chapter split over two files, and a chapter of three positions. */
const POSITIONS = [
  at(COVER, 1),
  at(CHAPTER_ONE, 2),
  at(CHAPTER_ONE, 3),
  at(CHAPTER_ONE_CONTINUED, 4),
  at(CHAPTER_TWO, 5),
  at(CHAPTER_TWO, 6),
  at(CHAPTER_TWO, 7),
];

/** Chapter one's sections live in its own file, which is how most books nest their contents. */
const TOC = [
  entry(CHAPTER_ONE, [entry(`${CHAPTER_ONE}#section-1`), entry(`${CHAPTER_ONE}#section-2`)]),
  entry(CHAPTER_TWO),
];

const STARTS = chapterStartsIn(TOC, POSITIONS);

const layout = (page: number, pageCount: number, sectionStarts: number[] = []) => ({
  page,
  pageCount,
  sectionStarts,
});

const pagesLeft = (locator: Locator, onScreen: ReturnType<typeof layout>) =>
  chapterProgressAt(locator, onScreen, STARTS, POSITIONS)?.pagesLeft;

test('a chapter starts at each resource the contents link to, sections and all', () => {
  expect(STARTS).toEqual([1, 2, 5]);
});

test('the sections of a resource are the contents entries pointing inside it', () => {
  expect(sectionIdsIn(TOC, CHAPTER_ONE)).toEqual(['section-1', 'section-2']);
  expect(sectionIdsIn(TOC, CHAPTER_TWO)).toEqual([]);
});

test('the resource on screen is counted in the pages it is laid out in', () => {
  expect(pagesLeft(at(CHAPTER_TWO, 5), layout(0, 10))).toBe(9);
  expect(pagesLeft(at(CHAPTER_TWO, 7), layout(9, 10))).toBe(0);
});

test('a smaller screen has more pages left in the same place', () => {
  expect(pagesLeft(at(CHAPTER_TWO, 5), layout(0, 20))).toBe(19);
});

test('a section ends on the page the next one starts on', () => {
  // The next section starts part-way down page 4, which the current one shares.
  expect(pagesLeft(at(CHAPTER_ONE, 2), layout(1, 8, [0.2, 4.5]))).toBe(3);
  // One starting at the top of page 4 leaves page 3 as this one's last.
  expect(pagesLeft(at(CHAPTER_ONE, 2), layout(1, 8, [4]))).toBe(2);
});

test('a section starting at the top of the page on screen is the one being read', () => {
  expect(pagesLeft(at(CHAPTER_ONE, 2), layout(4, 8, [4, 6]))).toBe(1);
});

test('a section beginning on the page on screen ends the current one here', () => {
  expect(pagesLeft(at(CHAPTER_ONE, 2), layout(4, 8, [4.5]))).toBe(0);
});

test('after the last section, a later resource of the chapter is estimated at this one’s pages per position', () => {
  // Four pages over two positions, and chapter one continues for one more position.
  expect(pagesLeft(at(CHAPTER_ONE, 2), layout(0, 4))).toBe(5);
});

test('the pages before the first chapter count as a chapter of their own', () => {
  expect(pagesLeft(at(COVER, 1), layout(0, 1))).toBe(0);
});

test('a place with no position number has no chapter progress', () => {
  const nowhere = new Locator({ href: CHAPTER_TWO, type: 'application/xhtml+xml' });

  expect(chapterProgressAt(nowhere, layout(0, 10), STARTS, POSITIONS)).toBeNull();
});
