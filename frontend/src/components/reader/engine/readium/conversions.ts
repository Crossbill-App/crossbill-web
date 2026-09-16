import type {
  EbookAppearance,
  EbookDecoration,
  EbookLocation,
  EbookTocEntry,
} from '@/components/reader/engine/EbookReader.ts';
import {
  DecorationStyleType,
  EpubPreferences,
  TextAlignment,
  type Decoration,
  type IKeyboardPeripheralsConfig,
} from '@readium/navigator';
import { Locator, LocatorLocations, LocatorText, type Link } from '@readium/shared';

/** ArrowRight and ArrowLeft, by the legacy key codes Readium's matcher compares. */
export const PAGE_TURN_KEYS: IKeyboardPeripheralsConfig = [
  { type: 'next_page', keyCombos: [{ keyCode: 39, suppressOnInteractiveElement: true }] },
  { type: 'previous_page', keyCombos: [{ keyCode: 37, suppressOnInteractiveElement: true }] },
];

const TEXT_ALIGNMENTS: Record<NonNullable<EbookAppearance['textAlign']>, TextAlignment> = {
  start: TextAlignment.start,
  justify: TextAlignment.justify,
};

// Eight of `EpubPreferences`' forty-odd fields: every one set here is one the
// reader can no longer inherit from the book. `null` rather than omitted,
// because the navigator merges and skips `undefined`, so an omission is no reset.
export const toEpubPreferences = (appearance: EbookAppearance): EpubPreferences =>
  new EpubPreferences({
    fontSize: appearance.fontSize,
    lineHeight: appearance.lineHeight,
    paragraphSpacing: appearance.paragraphSpacing,
    paragraphIndent: appearance.paragraphIndent,
    textAlign: appearance.textAlign === null ? null : TEXT_ALIGNMENTS[appearance.textAlign],
    columnCount: appearance.columnCount,
    backgroundColor: appearance.pageBackgroundColor,
    textColor: appearance.pageTextColor,
  });

export const toLocation = (locator: Locator): EbookLocation => ({
  href: locator.href,
  type: locator.type,
  title: locator.title,
  locations: {
    position: locator.locations.position,
    progression: locator.locations.progression,
    totalProgression: locator.locations.totalProgression,
    fragments: locator.locations.fragments,
  },
});

// Built rather than deserialized: `Locator.deserialize` refuses a location
// whose media type is empty, which is what a contents entry usually carries.
export const fromLocation = (location: EbookLocation): Locator => {
  const { cssSelector, ...locations } = location.locations;
  return new Locator({
    href: location.href,
    type: location.type,
    title: location.title,
    // Spelled twice: a jump reads the `otherLocations` map, but a decoration reaches its
    // frame as a structured clone, whose Map fails the library's `instanceof` check.
    locations: Object.assign(
      new LocatorLocations({
        ...locations,
        otherLocations: cssSelector ? new Map([['cssSelector', cssSelector]]) : undefined,
      }),
      cssSelector ? { cssSelector } : {}
    ),
    text: location.text && new LocatorText(location.text),
  });
};

// Hand-rolled rather than MUI's `alpha`, which agrees with it on every colour
// the seam admits: the engine speaks Readium and lodash, not the UI toolkit.
export const toRgba = (tint: string, opacity: number): string => {
  const hex = tint.replace('#', '');
  const channels = [0, 2, 4].map((offset) => parseInt(hex.slice(offset, offset + 2), 16));
  return `rgba(${channels.join(', ')}, ${opacity})`;
};

export const toDecoration = (decoration: EbookDecoration): Decoration => ({
  id: decoration.id,
  locator: fromLocation(decoration.location),
  style: {
    type: DecorationStyleType.Highlight,
    tint: toRgba(decoration.tint, decoration.opacity),
    // Readium's contrast pass darkens a tint to 3:1 against the page, which for
    // a wash the text sits on drives it towards 1:1 against the words instead.
    enforceContrast: false,
  },
});

export const tocEntriesFrom = (links: Link[]): EbookTocEntry[] =>
  links.map((link) => ({
    href: link.href,
    type: link.type ?? '',
    title: link.title ?? '',
    children: tocEntriesFrom(link.children?.items ?? []),
  }));
