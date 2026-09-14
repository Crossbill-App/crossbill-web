import type { Highlight, HighlightLocatorResponse, LocatorSchema } from '@/api/generated/model';
import type { EbookDecoration, EbookLocation } from '@/components/reader/EbookReader.ts';
import { DEFAULT_LABEL_COLOR } from '@/utils/colorUtils.ts';

// The label palette is saturated enough to carry a chip, and at full strength
// over a paragraph it is a wall rather than a highlight.
const TINT_OPACITY = 0.35;

// The API stores any string, so a colour set by hand may lack its hash; anything
// else the engine would draw invisible, and it would still take a tap.
const HEX_COLOR = /^#?[0-9a-f]{6}$/i;

const DECORATION_ID_PREFIX = 'highlight-';

const decorationId = (highlightId: number) => `${DECORATION_ID_PREFIX}${highlightId}`;

/** The highlight a drawn decoration stands for. */
export const highlightIdFrom = (decorationId: string): number =>
  Number(decorationId.slice(DECORATION_ID_PREFIX.length));

/** A highlight's locator in the engine's terms. */
export const toEbookLocation = (locator: LocatorSchema): EbookLocation => ({
  href: locator.href,
  type: locator.type,
  locations: {
    progression: locator.locations.progression ?? undefined,
    cssSelector: locator.locations.cssSelector ?? undefined,
  },
  text: {
    before: locator.text.before ?? undefined,
    highlight: locator.text.highlight ?? undefined,
    after: locator.text.after ?? undefined,
  },
});

const tintFor = (highlight: Highlight): string => {
  const color = highlight.label?.ui_color;
  return color && HEX_COLOR.test(color) ? `#${color.replace('#', '')}` : DEFAULT_LABEL_COLOR;
};

/** One book's highlights as the reader draws them: those the server placed, in their labels' colours. */
export const highlightDecorations = (
  locators: HighlightLocatorResponse[],
  highlights: Highlight[]
): EbookDecoration[] => {
  const byId = new Map(highlights.map((highlight) => [highlight.id, highlight]));
  return locators.flatMap(({ highlight_id, locator }) => {
    const highlight = byId.get(highlight_id);
    // No locator: the server could not place it, and a guess would mark the wrong words.
    // No highlight: deleted after the locators were fetched, which are never fetched again.
    if (!locator || !highlight) return [];
    return [
      {
        id: decorationId(highlight_id),
        location: toEbookLocation(locator),
        tint: tintFor(highlight),
        opacity: TINT_OPACITY,
      },
    ];
  });
};
