import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { useGetTags } from '@/api/generated/tags/tags.ts';
import { ReaderShell } from '@/components/reader/ReaderShell.tsx';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { HighlightViewDialog } from '@/pages/BookPage/Highlights/HighlightViewDialog';
import { useHighlightDialog } from '@/pages/BookPage/Highlights/hooks/useHighlightDialog.ts';
import { useNavigate, useParams, useSearch } from '@tanstack/react-router';
import { keyBy } from 'lodash';
import { useEffect, useMemo, useState } from 'react';

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
  const { highlightId } = useSearch({ from: '/book_/$bookId/read' });
  const navigate = useNavigate();
  const arrival = useArrivalAtAHighlight(highlightId);
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
        highlightId={arrival.target ?? undefined}
        onOpenHighlight={highlightDialog.open}
        onClose={() => void navigate({ to: '/book/$bookId', params: { bookId: bookId! } })}
      />

      {!arrival.isArriving && highlightDialog.activeItem && (
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

interface Arrival {
  /** The highlight this reader was opened at, or `null` for an ordinary open. */
  target: number | null;
  /** Whether the address still names it, and so whether its dialog is suppressed. */
  isArriving: boolean;
}

/**
 * `?highlightId=` on the way in, read once and then taken back out of the
 * address (M3.3, #747).
 *
 * The param does two different jobs and only one of them belongs to an arrival.
 * M3.2 gave it to the dialog: a decoration tapped in the book pushes it, and the
 * back button pops it, so a highlight opened in the reader is a place in history
 * and a link that can be pasted. M3.3 then made it a *destination* as well —
 * which is what a link from a highlight view means by it.
 *
 * Doing both at once put a dialog over the passage the reader had just asked to
 * be shown. They came to read it, so the arrival gets the jump and the emphasis
 * and nothing on top; the dialog is one tap away on the mark itself.
 *
 * So the param is consumed rather than merely acted on. It is latched here on
 * the first render, the dialog is held shut while it is still in the address,
 * and a `replace` strips it — which leaves the reader with an address that
 * describes what is on screen, a back button that leaves the reader in one step
 * rather than closing a dialog nobody opened, and a reload that opens the book
 * where the reader is rather than jumping again. Afterwards `target` is `null`
 * and the param means what M3.2 made it mean, tapping the arrival highlight
 * included.
 */
const useArrivalAtAHighlight = (highlightId: number | undefined): Arrival => {
  const navigate = useNavigate({ from: '/book/$bookId/read' });
  const [target, setTarget] = useState<number | null>(highlightId ?? null);

  // The address has stopped naming it, so the arrival is over. Asking the
  // address rather than remembering having asked for the strip: what ends an
  // arrival is the param actually being gone, and the reader is looking at an
  // unobscured page only once it is. A later tap changes the param too, which
  // ends the arrival just as truly — by then the strip has already happened.
  useResetOnChange([highlightId], () => setTarget(null));

  useEffect(() => {
    if (target === null) return;
    void navigate({ search: () => ({}), replace: true, resetScroll: false });
  }, [target, navigate]);

  return { target, isArriving: target !== null };
};
