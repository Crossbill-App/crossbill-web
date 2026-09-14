import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { useGetTags } from '@/api/generated/tags/tags.ts';
import { ReaderShell } from '@/components/reader/ReaderShell.tsx';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { HighlightViewDialog } from '@/pages/BookPage/Highlights/HighlightViewDialog';
import { useHighlightDialog } from '@/pages/BookPage/Highlights/hooks/useHighlightDialog.ts';
import { useNavigate, useParams, useSearch } from '@tanstack/react-router';
import { keyBy } from 'lodash';
import { useEffect, useMemo, useState } from 'react';

export const ReaderPage = () => {
  const { bookId } = useParams({ strict: false });
  const navigate = useNavigate();
  const { highlightId } = useSearch({ from: '/book_/$bookId/read' });
  const arrival = useArrivalAtAHighlight(highlightId);
  const { data: book } = useGetBookDetails(Number(bookId));
  const { data: tagsResponse } = useGetTags(Number(bookId));
  // A new array every render would be a new set of decorations every render.
  const highlights = useMemo(() => book?.chapters.flatMap((chapter) => chapter.highlights), [book]);
  const bookmarksByHighlightId = useMemo(
    () => keyBy(book?.bookmarks ?? [], 'highlight_id'),
    [book]
  );
  // `isMobile` only scrolls a list back to the highlight on close, and there is no list here.
  const highlightDialog = useHighlightDialog({ allHighlights: highlights ?? [], isMobile: false });

  return (
    <>
      <ReaderShell
        key={bookId}
        bookId={Number(bookId)}
        title={book?.title ?? ''}
        highlights={highlights}
        onOpenHighlight={highlightDialog.open}
        highlightId={arrival}
        onClose={() => void navigate({ to: '/book/$bookId', params: { bookId: String(bookId) } })}
      />
      {arrival === undefined && highlightDialog.activeItem && (
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

// `?highlightId=` is also the dialog's param, and a reader sent to a passage came to read it.
const useArrivalAtAHighlight = (highlightId: number | undefined) => {
  const navigate = useNavigate({ from: '/book/$bookId/read' });
  const [arrival, setArrival] = useState(highlightId);
  useResetOnChange([highlightId], () => setArrival(undefined));

  useEffect(() => {
    if (arrival === undefined) return;
    void navigate({ search: (prev) => ({ ...prev, highlightId: undefined }), replace: true });
  }, [arrival, navigate]);

  return arrival;
};
