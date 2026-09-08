import type { Highlight, HighlightLocatorResponse } from '@/api/generated/model';
import { DEFAULT_LABEL_COLOR } from '@/utils/colorUtils.ts';
import { alpha } from '@mui/material';
import { DecorationStyleType, type Decoration } from '@readium/navigator';
import { Locator } from '@readium/shared';

/**
 * The decoration group Crossbill's own highlights are drawn under.
 *
 * `@readium/navigator` keys decorations by group: `applyDecorations(list,
 * group)` replaces everything in that group and leaves every other group
 * alone, and an observer registered for a group hears only about its own
 * decorations. Reserving one name means the highlight layer can replace the
 * whole set on every change without touching whatever else may later be drawn
 * on the page — a search-result flash, a selection preview.
 */
export const HIGHLIGHT_DECORATION_GROUP = 'crossbill-highlights';

/**
 * How strongly a label's colour is laid over the book's own words.
 *
 * The label palette is chosen to carry a chip — saturated enough to read at a
 * glance against the page — and at full strength that same colour over a
 * paragraph is a wall rather than a highlight. Readium paints a `Highlight`
 * decoration with `mix-blend-mode: multiply` (`exclusion` on a dark page),
 * which already keeps dark text legible under any tint; the alpha is what keeps
 * the *page* legible, so a chapter marked end to end still reads as a book with
 * highlights in it rather than as a coloured block.
 */
const TINT_OPACITY = 0.35;

/**
 * Readium's contrast pass, and why this style opts out of it.
 *
 * `enforceContrast` darkens a tint in 10% steps until it stands at 3:1 against
 * the page — the right rule for an underline or an outline, which is a *line*
 * that has to be seen against the paper. A highlight is not a line: it is a
 * wash the text sits on top of, and driving it to 3:1 against the page drives
 * it towards 1:1 against the words, which is the one contrast that matters
 * here. It also undoes the alpha above, since darkening is how it gets there.
 *
 * The blend mode is what carries the reading theme instead, and it is
 * Readium's own: `multiply` leaves dark text on a light page untouched under
 * any tint, and a dark page switches to `exclusion` without being asked.
 */
const ENFORCE_CONTRAST = false;

/**
 * A decoration id, and how to read a highlight back out of one.
 *
 * The id is the only thing an activation event carries back that we chose, so
 * it has to be reversible. Prefixed rather than a bare number because it also
 * has to be recognisable in a frame's DOM when something has gone wrong.
 */
const DECORATION_ID_PREFIX = 'highlight-';

const decorationId = (highlightId: number) => `${DECORATION_ID_PREFIX}${highlightId}`;

/** The highlight a decoration stands for, or `null` if it is not one of ours. */
export const activatedHighlightId = (decorationId: string): number | null => {
  if (!decorationId.startsWith(DECORATION_ID_PREFIX)) return null;
  const id = Number(decorationId.slice(DECORATION_ID_PREFIX.length));
  return Number.isInteger(id) ? id : null;
};

/**
 * Six hex digits, with or without the leading hash.
 *
 * `ui_color` reaches the browser as stored text, and `alpha()` throws on a
 * value it cannot parse — which in here would take the whole reader down over
 * one malformed label. Checked rather than caught so the fallback is a
 * decision instead of an exception handler.
 */
const HEX_COLOR = /^#?[0-9a-f]{6}$/i;

/** The tint a highlight is drawn in: its label's colour, or the palette's quietest. */
const tintFor = (highlight: Highlight | undefined): string => {
  const color = highlight?.label?.ui_color;
  return alpha(color && HEX_COLOR.test(color) ? color : DEFAULT_LABEL_COLOR, TINT_OPACITY);
};

/**
 * The decorations a navigator draws for one book's highlights.
 *
 * Two reads meet here, and they are separate on purpose. The *places* come
 * from the web reader's own locator endpoint, which derives them from the
 * canonical xpointers against the EPUB (ADR-0004 §2) and is the expensive half;
 * the *colours* come from the book-details payload the reader already holds,
 * which is where a highlight's resolved label lives. Neither waits for the
 * other to be fetched, and a highlight missing from the second is still drawn —
 * in the default tint — rather than dropped, because a highlight the reader can
 * see in the book matters more than the shade it is shown in.
 *
 * Highlights carrying a reason instead of a locator produce nothing at all.
 * There is genuinely nowhere to draw them, and inventing a place is the exact
 * failure ADR-0004 §5 withholds the locator to prevent. Telling the reader they
 * exist is M3.4's job, in the chrome rather than on the page.
 *
 * The href needs no translation: the API states a locator in the coordinates
 * the manifest publishes (`resources/OEBPS/chapter1.xhtml`), which is what the
 * navigator matches a decoration against when it decides which frame the
 * decoration belongs in.
 */
export const highlightDecorations = (
  locators: HighlightLocatorResponse[],
  highlights: Highlight[]
): Decoration[] => {
  const byId = new Map(highlights.map((highlight) => [highlight.id, highlight]));
  return locators.flatMap((placed) => {
    if (!placed.locator) return [];
    const locator = Locator.deserialize(placed.locator);
    if (!locator) return [];
    return [
      {
        id: decorationId(placed.highlight_id),
        locator,
        style: {
          type: DecorationStyleType.Highlight,
          tint: tintFor(byId.get(placed.highlight_id)),
          enforceContrast: ENFORCE_CONTRAST,
        },
      },
    ];
  });
};
