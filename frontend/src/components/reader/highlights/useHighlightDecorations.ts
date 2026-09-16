import { useGetBookHighlightLocators } from '@/api/generated/highlights/highlights.ts';
import type { Highlight } from '@/api/generated/model';
import type { EbookDecoration } from '@/components/reader/engine/EbookReader.ts';
import { highlightDecorations } from '@/components/reader/highlights/decorations.ts';
import { LOCATORS_QUERY } from '@/components/reader/highlights/highlightLocatorsQuery.ts';
import { useMemo } from 'react';

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
