import { ReaderIcon } from '@/theme/Icons.tsx';
import { IconButton, Tooltip, type IconButtonProps } from '@mui/material';
import { createLink, useMatch } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';

// A link rather than a click handler, so the reader can be opened in a new tab
// and its address copied.
const ReaderLinkButton = createLink(IconButton);

export interface OpenInReaderButtonProps {
  bookId: number;
  highlightId?: number;
  chapterId?: number;
  size?: IconButtonProps['size'];
  sx?: IconButtonProps['sx'];
}

/**
 * Opens the book in the reader, at a highlight or a chapter when given one;
 * nothing while already reading it.
 */
export const OpenInReaderButton = ({
  bookId,
  highlightId,
  chapterId,
  size,
  sx,
}: OpenInReaderButtonProps) => {
  const { t } = useTranslation();
  // Selected down to the book id, so a list of these does not re-render on every search change.
  const readingBookId = useMatch({
    from: '/book_/$bookId/read',
    shouldThrow: false,
    select: (match) => match.params.bookId,
  });

  if (readingBookId === String(bookId)) return null;

  const label =
    chapterId === undefined
      ? t('components.openInReaderButton.book')
      : t('components.openInReaderButton.chapter');

  return (
    <Tooltip title={label}>
      <ReaderLinkButton
        to="/book/$bookId/read"
        params={{ bookId: String(bookId) }}
        search={{ highlightId, chapterId }}
        aria-label={label}
        size={size}
        sx={sx}
      >
        <ReaderIcon />
      </ReaderLinkButton>
    </Tooltip>
  );
};
