/**
 * The icon size scale. Three steps, and never below `ui` for anything
 * clickable — the tag-group actions used to be 14px in `text.disabled`, the
 * smallest and lowest-contrast targets in the app, one of which deleted a
 * group.
 */
export const ICON_SIZE = {
  /** Inline with text: metadata, counts, markers inside a chip or swatch. */
  inline: 16,
  /** UI chrome: section headers, and controls in a toolbar or a row. */
  ui: 20,
  /** Prominent: the quote mark that opens a highlight. */
  prominent: 24,
} as const;
