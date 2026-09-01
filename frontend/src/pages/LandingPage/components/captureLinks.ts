import type { RecentCapture } from '@/api/generated/model';
import { linkOptions } from '@tanstack/react-router';

/** Where a capture opens: the same book-page targets global search uses. */
export const captureLinkProps = (capture: RecentCapture) => {
  const params = { bookId: String(capture.book_id) };

  return capture.kind === 'highlight'
    ? linkOptions({
        to: '/book/$bookId/highlights',
        params,
        search: { highlightId: capture.id },
      })
    : linkOptions({ to: '/book/$bookId/notes', params, search: { noteId: capture.id } });
};

/**
 * Where the captures the day's cap left out are: that book's highlights,
 * filtered to that day, so the count in the link is one click from verifiable.
 */
export const moreInBookLinkProps = (capture: RecentCapture) =>
  linkOptions({
    to: '/book/$bookId/highlights',
    params: { bookId: String(capture.book_id) },
    search: { from: capture.day, to: capture.day },
  });
