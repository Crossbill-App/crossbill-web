import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { ReaderIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { IconButton, Tooltip, type IconButtonProps } from '@mui/material';
import { createLink, useMatchRoute } from '@tanstack/react-router';

const LABEL = 'Open in reader';

/**
 * An `IconButton` that is a link.
 *
 * A link rather than a click handler because this goes to a page: it can be
 * opened in a new tab, its address can be copied, and the browser shows where
 * it leads. `createLink` is how the router wraps a component that is not one of
 * its own, which is the same thing the book's own nav does for its list items.
 */
const ReaderLinkButton = createLink(IconButton);

interface OpenInReaderButtonProps {
  bookId: number;
  highlightId: number;
  size?: IconButtonProps['size'];
}

/**
 * Takes the reader to this highlight in the book, and renders nothing where
 * that would mean nothing (M3.3, #747).
 *
 * Two things make it nothing. **A book with no EPUB has no reader**, exactly as
 * the book's own Read tab is absent for one — and while it is unknown whether
 * there is an EPUB the action stays away, because appearing late is a smaller
 * surprise than appearing and then vanishing under the pointer. **A reader
 * already in the reader is there**: the same dialog opens over the book itself,
 * where an action leading to the page it is already on would be a link to
 * nowhere.
 *
 * It reads the book's details itself rather than being told, so that the three
 * places a highlight is listed — the highlights tab, a chapter's dialog, a
 * note's linked highlights — need know nothing about EPUBs to offer it. That is
 * one query subscription per row on a page that renders a book's whole highlight
 * list at once (ADR-0003), which is affordable precisely because it is the query
 * those rows are already made of: it is cached, it is not refetched for this,
 * and it changes only when the highlights themselves do.
 */
export const OpenInReaderButton = ({
  bookId,
  highlightId,
  size = 'medium',
}: OpenInReaderButtonProps) => {
  const { data: book } = useGetBookDetails(bookId);
  const matchRoute = useMatchRoute();
  const alreadyReading = !!matchRoute({
    to: '/book/$bookId/read',
    params: { bookId: String(bookId) },
  });

  if (book?.has_ebook !== true || alreadyReading) return null;

  return (
    <Tooltip title={LABEL}>
      <ReaderLinkButton
        to="/book/$bookId/read"
        params={{ bookId: String(bookId) }}
        search={{ highlightId }}
        aria-label={LABEL}
        size={size}
        sx={{ color: 'text.secondary' }}
      >
        <ReaderIcon sx={{ fontSize: size === 'small' ? ICON_SIZE.ui : undefined }} />
      </ReaderLinkButton>
    </Tooltip>
  );
};
