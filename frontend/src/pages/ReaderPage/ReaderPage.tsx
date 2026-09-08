import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { useGetTags } from '@/api/generated/tags/tags.ts';
import { ReaderShell } from '@/components/reader/ReaderShell.tsx';
import { HighlightViewDialog } from '@/pages/BookPage/Highlights/HighlightViewDialog';
import { useHighlightDialog } from '@/pages/BookPage/Highlights/hooks/useHighlightDialog.ts';
import { useNavigate, useParams, useSearch } from '@tanstack/react-router';
import { keyBy } from 'lodash';
import { useMemo } from 'react';

/**
 * Reading a book in the browser, at `/book/{id}/read`.
 *
 * The page itself is thin on purpose: it turns the URL into a book, borrows
 * the title from the book-details query the book page has usually already
 * filled, and hands both to the reader. Everything else — the two credentials,
 * the navigator, the chrome — belongs to `ReaderShell`.
 *
 * What it does own is the highlight dialog, because that is where the data for
 * it already is. The same book-details payload that supplies the title carries
 * every highlight of the book with its resolved label, which is both what
 * `HighlightViewDialog` renders and where a decoration gets its colour — so the
 * reader draws highlights in the colours the book page shows them in, from one
 * fetch, rather than from a second view of the same rows. The reader is never
 * held up for it: the book opens with no title and no decorations and gains
 * both when the query answers.
 */
export const ReaderPage = () => {
  const { bookId } = useParams({ strict: false });
  // The one search param this route takes, and it means two things at once: the
  // book opens *at* that highlight (M3.3, #747) and the highlight's own dialog
  // opens over it. A link from a highlight view says "show me this highlight",
  // and showing somebody a highlight means both putting it in front of them and
  // letting them read it with its notes and tags — the reader is what the
  // passage is *in*, and the dialog is what the highlight *is*. Closing the
  // dialog drops the param and leaves the book where it landed, which is the
  // point: what is behind the dialog is the passage they came for.
  const { highlightId } = useSearch({ from: '/book_/$bookId/read' });
  const navigate = useNavigate();
  const { data: book } = useGetBookDetails(Number(bookId));
  const { data: tagsResponse } = useGetTags(Number(bookId));

  // `undefined` until the book has answered, which the decoration layer reads
  // as "nothing is known to be missing yet" rather than as "this book has no
  // highlights". The two call for different drawing, and for different answers
  // to a decoration being tapped.
  const allHighlights = useMemo(
    () => book?.chapters.flatMap((chapter) => chapter.highlights),
    [book]
  );
  const bookmarksByHighlightId = useMemo(
    () => keyBy(book?.bookmarks ?? [], 'highlight_id'),
    [book]
  );

  // `isMobile` is what asks the dialog to scroll a list back to the highlight
  // it closed on. There is no list here — there is a book — so it is false at
  // every width.
  const highlightDialog = useHighlightDialog({
    allHighlights: allHighlights ?? [],
    isMobile: false,
  });

  return (
    <>
      {/* Keyed by the book, so opening a different one gets a fresh navigator,
          a fresh publication cookie and a fresh place in the text rather than
          one book's reader being asked to become another's. */}
      <ReaderShell
        key={bookId}
        bookId={Number(bookId)}
        title={book?.title ?? ''}
        highlights={allHighlights}
        highlightId={highlightId}
        onOpenHighlight={highlightDialog.open}
        onClose={() => void navigate({ to: '/book/$bookId', params: { bookId: bookId! } })}
      />

      {highlightDialog.activeItem && (
        <HighlightViewDialog
          controller={highlightDialog}
          bookId={Number(bookId)}
          availableTags={tagsResponse?.items ?? []}
          bookmarksByHighlightId={bookmarksByHighlightId}
        />
      )}
    </>
  );
};
