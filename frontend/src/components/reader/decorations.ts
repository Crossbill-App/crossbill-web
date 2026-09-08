import { getGetBookHighlightLocatorsQueryKey } from '@/api/generated/highlights/highlights.ts';
import type {
  CollectionResponseHighlightLocatorResponse,
  Highlight,
  HighlightLocatorResponse,
} from '@/api/generated/model';
import { DEFAULT_LABEL_COLOR } from '@/utils/colorUtils.ts';
import { alpha } from '@mui/material';
import { DecorationStyleType, type Decoration } from '@readium/navigator';
import { Locator } from '@readium/shared';
import type { QueryClient } from '@tanstack/react-query';

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
 * How a highlight the reader was *brought here for* announces itself, and why
 * it is the tint that does it.
 *
 * A jump from a highlight view (M3.3, #747) lands on a page that may already
 * carry a dozen marks, and the reader has to be able to tell which one they
 * clicked. Readium's decoration styles have no active or selected state to
 * borrow — the built-ins are shapes (highlight, underline, outline) with a
 * tint, and nothing that means "this one" — so what is available is the tint
 * itself, and `applyDecorations` diffs by decoration, so re-offering the set
 * with one entry brighter redraws exactly that one.
 *
 * A ramp rather than a flash held and dropped: `::highlight()` backgrounds are
 * not animatable, so the fade has to be drawn rather than declared, and a
 * handful of steps is enough for the eye to read it as one mark settling rather
 * than as the page changing several times.
 *
 * The last step *is* `TINT_OPACITY`, and it is there rather than implied. The
 * ramp used to end on 0.44 and then stop, which put an unheld ninth of the
 * fade's range into the moment the emphasis was dropped — a small snap at
 * exactly the point the eye had been trained on the mark. Redrawing the last
 * step costs nothing either: it is the decoration the highlight already has, so
 * `applyDecorations` diffs it away.
 */
const EMPHASIS_OPACITIES = [0.75, 0.62, 0.52, 0.44, TINT_OPACITY] as const;

/** How long each step of that ramp is held. */
const EMPHASIS_STEP_MS = 260;

/** The emphasis ramp, and how long a step of it lasts. */
export const EMPHASIS = { opacities: EMPHASIS_OPACITIES, stepMs: EMPHASIS_STEP_MS } as const;

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
 * `ui_color` reaches the browser as stored text and is written by a colour
 * picker, a KOReader sync and whatever has edited the database since, so both
 * spellings turn up. It is normalised rather than merely matched: `alpha()`
 * parses `#F59E0B` and *throws* on `F59E0B`, and an exception raised while
 * building decorations is thrown during a render that has a book in it.
 */
const HEX_COLOR = /^#?[0-9a-f]{6}$/i;

/** The tint a highlight is drawn in: its label's colour, or the palette's quietest. */
const tintFor = (highlight: Highlight | undefined, opacity: number): string => {
  const color = highlight?.label?.ui_color;
  const hex = color && HEX_COLOR.test(color) ? `#${color.replace('#', '')}` : DEFAULT_LABEL_COLOR;
  return alpha(hex, opacity);
};

/**
 * One highlight drawn brighter than the rest, while the emphasis lasts.
 *
 * The colour is still the label's own: what marks the highlight out is how
 * strongly it is laid on, not a colour of the reader's choosing, so a reader
 * who knows their yellow highlights still sees a yellow one.
 */
export interface DecorationEmphasis {
  highlightId: number;
  opacity: number;
}

/**
 * The decorations a navigator draws for one book's highlights.
 *
 * Two reads meet here, and they are separate on purpose. The *places* come
 * from the web reader's own locator endpoint, which derives them from the
 * canonical xpointers against the EPUB (ADR-0004 §2) and is the expensive half;
 * the *identities and colours* come from the book-details payload the reader
 * already holds, which is where a highlight's resolved label lives.
 *
 * `highlights` being `undefined` is what tells the two apart, and the
 * distinction is load-bearing rather than defensive:
 *
 * - **Not loaded yet.** Draw every placed locator, in the default tint. A
 *   highlight the reader can see in the book matters more than the shade it is
 *   shown in, and the colour arrives a moment later without redrawing anything
 *   else.
 * - **Loaded.** Draw only the locators the book still has a highlight for. The
 *   two reads are invalidated together but settle separately, and a locator
 *   list that still lists a highlight the book no longer has would otherwise be
 *   drawn as a grey ghost — one that opens nothing when tapped, because there
 *   is no highlight left for the dialog to show.
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
  highlights: Highlight[] | undefined,
  emphasis: DecorationEmphasis | null = null
): Decoration[] => {
  const byId = new Map((highlights ?? []).map((highlight) => [highlight.id, highlight]));
  return locators.flatMap((placed) => {
    if (!placed.locator) return [];
    if (highlights !== undefined && !byId.has(placed.highlight_id)) return [];
    const locator = Locator.deserialize(placed.locator);
    if (!locator) return [];
    const opacity = emphasis?.highlightId === placed.highlight_id ? emphasis.opacity : TINT_OPACITY;
    return [
      {
        id: decorationId(placed.highlight_id),
        locator,
        style: {
          type: DecorationStyleType.Highlight,
          tint: tintFor(byId.get(placed.highlight_id), opacity),
          enforceContrast: ENFORCE_CONTRAST,
        },
      },
    ];
  });
};

/** Whether this book's locator list has a place to draw that highlight at. */
export const isPlaced = (
  locators: HighlightLocatorResponse[],
  highlightId: number | null
): boolean =>
  highlightId !== null &&
  locators.some((placed) => placed.highlight_id === highlightId && !!placed.locator);

/**
 * Forget the locators of highlights that have just been deleted.
 *
 * A write-through rather than an invalidation, and the difference is the point.
 * Invalidating would send the server the most expensive question in the app —
 * place every highlight in this book (ADR-0004 *Amendment 5*) — to be told
 * exactly what is already known: the survivors are where they always were, and
 * a deleted highlight has no locator by virtue of being deleted. It would also
 * open a window in which the refetched book has lost the highlight while the
 * stale locator list still has it, which is drawn as a grey mark that opens
 * nothing.
 *
 * Lives here, with the reader's other decoration knowledge, and is called from
 * the mutation that deletes: `cacheEvents` is for invalidation expressed as
 * domain events, and explicitly not for write-through.
 *
 * A cache with nothing in it is left alone. Seeding one would mean writing an
 * answer for a book whose locators nobody has asked for.
 */
export const forgetHighlightLocators = (
  queryClient: QueryClient,
  bookId: number,
  deletedIds: number[]
): void => {
  const gone = new Set(deletedIds);
  queryClient.setQueryData<CollectionResponseHighlightLocatorResponse>(
    getGetBookHighlightLocatorsQueryKey(bookId),
    (current) =>
      current && {
        ...current,
        items: current.items.filter((placed) => !gone.has(placed.highlight_id)),
      }
  );
};

/**
 * Whether a decoration is drawn under this point of a publication frame.
 *
 * The tap zones need to know, and they need to know *synchronously*. Readium
 * reports an activation over `postMessage`, so it lands a task after the
 * `pointerup` that caused it — by which time an untreated tap near an edge has
 * already turned the page, and the reader gets the highlight they asked for
 * plus a page they did not. The navigator's own `_decorationActivationConsumed`
 * does not help: it gates Readium's built-in pager, which this reader disables
 * outright by claiming `tap` and `click`.
 *
 * So the hit test is done here, against the ranges Readium registered for its
 * own drawing. That is what makes it agree with what is painted rather than
 * with a second computation of where the highlights ought to be: these are the
 * exact ranges the decorations were laid on.
 *
 * It reads the CSS Custom Highlight API, which is the path Readium takes
 * wherever the browser has it — Chromium and WebKit both do. A browser without
 * it falls back to Readium's absolutely-positioned boxes, which sit in a
 * `pointer-events: none` shadow root and cannot be hit-tested at all; there the
 * answer is `false` and the behaviour is what it was before this existed.
 */
/**
 * A publication frame's own realm, in the parts this hit test needs.
 *
 * `CSS.highlights` is absent on browsers without the Custom Highlight API,
 * hence the optionals. What it holds is a map of highlight name to a set of
 * ranges, and those ranges are *not* `instanceof Range` here: they were made in
 * the frame's document, which is a realm of its own — the same trap the tap
 * zones' `nearestInteractive` documents for `Element`, and worth restating
 * because the constructor is even named `Range`, so a debugger agrees with the
 * check that fails. They are duck-typed on `getClientRects` instead, which is
 * the only thing wanted from them.
 */
interface PublicationRealm {
  CSS?: { highlights?: Iterable<[string, Iterable<unknown>]> };
}

interface Measurable {
  getClientRects: () => Iterable<DOMRect>;
}

const isMeasurable = (value: unknown): value is Measurable =>
  typeof (value as Measurable | null)?.getClientRects === 'function';

export const decorationCoversPoint = (
  frameWindow: Window,
  clientX: number,
  clientY: number
): boolean => {
  const highlights = (frameWindow as unknown as PublicationRealm).CSS?.highlights;
  if (!highlights) return false;
  for (const [, ranges] of highlights) {
    for (const range of ranges) {
      if (!isMeasurable(range)) continue;
      for (const rect of range.getClientRects()) {
        if (
          clientX >= rect.left &&
          clientX <= rect.right &&
          clientY >= rect.top &&
          clientY <= rect.bottom
        )
          return true;
      }
    }
  }
  return false;
};
