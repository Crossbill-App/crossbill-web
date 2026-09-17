import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { useGetTags } from '@/api/generated/tags/tags.ts';
import { targetOf } from '@/components/reader/opening/useReaderLanding.ts';
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
  const { highlightId, chapterId } = useSearch({ from: '/book_/$bookId/read' });
  const arrival = useArrivalAtAPlace(highlightId, chapterId);
  const { data: book } = useGetBookDetails(Number(bookId));
  const { data: tagsResponse } = useGetTags(Number(bookId));
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
        onOpenHighlight={highlightDialog.open}
        target={arrival}
        onClose={() => void navigate({ to: '/book/$bookId', params: { bookId: String(bookId) } })}
      />
      {arrival === null && highlightDialog.activeItem && (
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

// A reader sent to a place came to read it. `?highlightId=` is also the in-reader
// dialog's own param, so a tap on a highlight resets this to `null`, not to itself.
const useArrivalAtAPlace = (highlightId: number | undefined, chapterId: number | undefined) => {
  const navigate = useNavigate({ from: '/book/$bookId/read' });
  const [arrival, setArrival] = useState(() => targetOf(highlightId, chapterId));
  useResetOnChange([highlightId, chapterId], () => setArrival(null));

  useEffect(() => {
    if (arrival === null) return;
    void navigate({
      search: (prev) => ({ ...prev, highlightId: undefined, chapterId: undefined }),
      replace: true,
    });
  }, [arrival, navigate]);

  return arrival;
};
