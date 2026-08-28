import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { useMemo } from 'react';

/**
 * How many notes are linked to each highlight in the book.
 *
 * Derived from the book's notes because the highlight payload carries no note
 * links. Shares a query key with the book header's own notes fetch, so the
 * lists that use it make no new request.
 */
export const useNoteCountsByHighlight = (): Record<number, number> => {
  const { book } = useBookPage();
  const { data } = useGetNotesForBook(book.id);

  return useMemo(() => {
    const counts: Record<number, number> = {};
    for (const note of data?.items ?? []) {
      for (const highlightId of note.highlight_ids) {
        counts[highlightId] = (counts[highlightId] ?? 0) + 1;
      }
    }
    return counts;
  }, [data]);
};
