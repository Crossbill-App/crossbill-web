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
 * Where the captures the feed left out are, for the kind the count is of: a
 * highlight's list filtered to that day, so the count is one click from
 * verifiable, a note's unfiltered, the notes route having no day filter.
 */
export const moreInBookLinkProps = (capture: RecentCapture) => {
  const params = { bookId: String(capture.book_id) };

  return capture.kind === 'highlight'
    ? linkOptions({
        to: '/book/$bookId/highlights',
        params,
        search: { from: capture.day, to: capture.day },
      })
    : linkOptions({ to: '/book/$bookId/notes', params });
};
