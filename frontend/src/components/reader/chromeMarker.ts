/**
 * The attribute every piece of the reader's own UI carries.
 *
 * The reader listens for arrow keys on the window, because the book has to
 * turn pages wherever the focus happens to be. That makes the chrome's own
 * controls ambiguous: an arrow on the font-size slider is a font size, not a
 * page. Marking the chrome lets one `closest()` call answer "is this key meant
 * for us or for the book", and it works for the contents drawer and the
 * appearance popover too, which MUI portals out of the reader's React tree
 * where no ancestor check in JSX terms would find them.
 */
export const CHROME_MARKER = 'data-reader-chrome';

/** Spreadable form, so a component can mark itself without repeating the name. */
export const chromeMarkerProps = { [CHROME_MARKER]: true } as const;
