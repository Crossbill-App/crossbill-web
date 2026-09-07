/**
 * The decoration group Crossbill's own highlights are drawn under.
 *
 * `@readium/navigator` keys decorations by group: `applyDecorations(list,
 * group)` replaces everything in that group and leaves every other group
 * alone, and an observer registered for a group hears only about its own
 * decorations. Reserving one name here means the highlight layer (M3.2) can
 * replace the whole set on every change without touching whatever else may
 * later be drawn on the page — a search-result flash, a selection preview.
 *
 * Nothing applies decorations yet. `ReaderShell` registers an observer for the
 * group so the seam is wired and provably reaches the navigator; the handlers
 * are no-ops until there is something to activate.
 */
export const HIGHLIGHT_DECORATION_GROUP = 'crossbill-highlights';
