/** Clamp text to `lines` rendered lines: a word cap cuts prose mid-word, markdown mid-fence. */
export const clampToLines = (lines: number) => ({
  display: '-webkit-box',
  WebkitLineClamp: lines,
  WebkitBoxOrient: 'vertical' as const,
  overflow: 'hidden',
});
