import type { EbookAppearance, EbookLocation } from '@/components/reader/engine/EbookReader.ts';
import {
  fromLocation,
  toEpubPreferences,
  toLocation,
  toRgba,
  tocEntriesFrom,
} from '@/components/reader/engine/readium/conversions.ts';
import { TextAlignment } from '@readium/navigator';
import { Links, Locator } from '@readium/shared';
import { aManifest } from '@tests/fixtures/publication';
import { expect, test } from 'vitest';

/** A highlight's place in a chapter, as the seam spells one. */
const A_HIGHLIGHT: EbookLocation = {
  href: 'resources/OEBPS/chapter1.xhtml',
  type: 'application/xhtml+xml',
  title: 'On Attention',
  locations: {
    position: 4,
    progression: 0.25,
    totalProgression: 0.125,
    fragments: ['#first'],
    cssSelector: '#first > p:nth-child(1)',
  },
  text: { before: 'Attention is the ', highlight: 'rarest and purest', after: ' form' },
};

const AN_APPEARANCE: EbookAppearance = {
  fontSize: 1.2,
  lineHeight: 1.5,
  paragraphSpacing: 1,
  paragraphIndent: 0,
  textAlign: 'start',
  columnCount: 1,
  pageBackgroundColor: '#fffaf0',
  pageTextColor: '#1a1a1a',
};

test('a selector reaches the frame both ways a Readium locator can carry it', () => {
  const locator = fromLocation(A_HIGHLIGHT);

  expect(locator.locations.otherLocations?.get('cssSelector')).toBe('#first > p:nth-child(1)');
  // The structured-clone route, which a decoration crossing into a frame takes.
  expect((locator.locations as { cssSelector?: string }).cssSelector).toBe(
    '#first > p:nth-child(1)'
  );
});

test('a contents entry declaring no media type still becomes a locator', () => {
  const entry: EbookLocation = { href: 'resources/OEBPS/chapter2.xhtml', type: '', locations: {} };

  expect(fromLocation(entry).href).toBe('resources/OEBPS/chapter2.xhtml');
  expect(fromLocation(entry).type).toBe('');
  // Which is why it is built rather than deserialized.
  expect(Locator.deserialize({ href: entry.href, type: entry.type })).toBeUndefined();
});

test('a location survives the round trip through Readium and back', () => {
  const location = toLocation(fromLocation(A_HIGHLIGHT));

  expect(location.href).toBe('resources/OEBPS/chapter1.xhtml');
  expect(location.type).toBe('application/xhtml+xml');
  expect(location.title).toBe('On Attention');
  expect(location.locations.position).toBe(4);
  expect(location.locations.progression).toBe(0.25);
  expect(location.locations.totalProgression).toBe(0.125);
  expect(location.locations.fragments).toEqual(['#first']);
});

test('the contents keep their nesting, and say nothing rather than undefined', () => {
  const links = Links.deserialize([...aManifest().toc, { href: 'resources/OEBPS/colophon.xhtml' }]);

  const entries = tocEntriesFrom(links?.items ?? []);

  expect(entries.map((entry) => entry.title)).toEqual(['On Attention', 'Part two', '']);
  // A part heading links nowhere; its chapters do.
  expect(entries[1].children.map((child) => child.href)).toEqual([
    'resources/OEBPS/chapter2.xhtml',
  ]);
  expect(entries[0].type).toBe('');
  expect(entries[0].children).toEqual([]);
});

test('a hex tint and an opacity become the rgba Readium paints with', () => {
  expect(toRgba('#f59e0b', 0.35)).toBe('rgba(245, 158, 11, 0.35)');
});

test('an alignment the book should decide for itself is passed on as a reset', () => {
  expect(toEpubPreferences({ ...AN_APPEARANCE, textAlign: null }).textAlign).toBeNull();
  expect(toEpubPreferences(AN_APPEARANCE).textAlign).toBe(TextAlignment.start);
});
