import { useGetBookHighlightLocators } from '@/api/generated/highlights/highlights.ts';
import type { Highlight } from '@/api/generated/model';
import { highlightDecorations } from '@/components/reader/decorations.ts';
import type { EbookDecoration } from '@/components/reader/EbookReader.ts';
import { useMemo } from 'react';

const LOCATORS_QUERY = {
  // Only a replaced EPUB moves a locator, so a focus refetch would place the whole book
  // again for nothing; and a failure leaves the book unmarked, which is still the book.
  retry: false,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
} as const;

/** The decorations for one book's highlights, the same array for as long as neither input changes. */
export const useHighlightDecorations = (
  bookId: number,
  highlights: Highlight[] | undefined
): EbookDecoration[] => {
  const { data } = useGetBookHighlightLocators(bookId, { query: LOCATORS_QUERY });
  return useMemo(
    () => highlightDecorations(data?.items ?? [], highlights ?? []),
    [data, highlights]
  );
};
