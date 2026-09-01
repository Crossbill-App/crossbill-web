const previewWordCount = 40;

/** The visible text of a highlight in a list: leading ellipsis for a mid-sentence start, then a word cap. */
export const buildPreviewText = (text: string): string => {
  const startsWithLowercase =
    text.length > 0 && text[0] === text[0].toLowerCase() && text[0] !== text[0].toUpperCase();
  const formattedText = startsWithLowercase ? `...${text}` : text;

  const words = formattedText.split(/\s+/);

  return words.length > previewWordCount
    ? words.slice(0, previewWordCount).join(' ') + '...'
    : formattedText;
};
