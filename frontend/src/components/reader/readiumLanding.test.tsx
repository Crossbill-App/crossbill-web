import { landingFor } from '@/components/reader/readiumLanding.ts';
import { Locator } from '@readium/shared';
import { expect, test } from 'vitest';

const CHAPTER_ONE = 'resources/OEBPS/chapter1.xhtml';
const CHAPTER_TWO = 'resources/OEBPS/chapter2.xhtml';

const at = (href: string, locations: Record<string, number>): Locator =>
  new Locator({ href, type: 'application/xhtml+xml' }).copyWithLocations(locations);

/** Two resources, the second of them long enough to be split across three positions. */
const POSITIONS = [
  at(CHAPTER_ONE, { position: 1, progression: 0, totalProgression: 0 }),
  at(CHAPTER_TWO, { position: 2, progression: 0, totalProgression: 0.25 }),
  at(CHAPTER_TWO, { position: 3, progression: 0.33, totalProgression: 0.5 }),
  at(CHAPTER_TWO, { position: 4, progression: 0.66, totalProgression: 0.75 }),
];

test('a locator naming a resource this publication has not got lands nowhere', () => {
  const target = at('resources/OEBPS/appendix.xhtml', { progression: 0.5 });

  expect(landingFor(target, POSITIONS)).toBeNull();
});

test('a locator carrying no progression lands on its resource first position', () => {
  const target = new Locator({ href: CHAPTER_TWO, type: 'application/xhtml+xml' });

  expect(landingFor(target, POSITIONS)?.locations.position).toBe(2);
});

test('a progression inside a split resource lands on the entry covering it', () => {
  const target = at(CHAPTER_TWO, { progression: 0.5 });

  const landing = landingFor(target, POSITIONS);

  expect(landing?.locations.position).toBe(3);
  expect(landing?.locations.totalProgression).toBe(0.5);
});

test('the landing is the target wearing the entry numbers, not the entry itself', () => {
  const target = new Locator({
    href: CHAPTER_TWO,
    type: 'application/xhtml+xml',
    title: 'On Memory',
  }).copyWithLocations({ position: 900, progression: 0.5, totalProgression: 0.99 });

  const landing = landingFor(target, POSITIONS);

  expect(landing?.href).toBe(CHAPTER_TWO);
  expect(landing?.type).toBe('application/xhtml+xml');
  expect(landing?.title).toBe('On Memory');
  // The progression places the reader in the resource; the position only has to
  // index the list the publication has today.
  expect(landing?.locations.progression).toBe(0.5);
  expect(landing?.locations.position).toBe(3);
  expect(landing?.locations.totalProgression).toBe(0.5);
});
