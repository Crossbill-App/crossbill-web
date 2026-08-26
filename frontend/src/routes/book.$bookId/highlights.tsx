import { HighlightsPage } from '@/pages/BookPage/Highlights/HighlightsPage';
import { parseDateSearchParam } from '@/pages/BookPage/common/highlightDates.ts';
import { createFileRoute } from '@tanstack/react-router';

type HighlightsSearch = {
  search?: string;
  tagId?: number;
  labelId?: number;
  highlightId?: number;
  from?: string;
  to?: string;
};

export const Route = createFileRoute('/book/$bookId/highlights')({
  component: HighlightsPage,
  validateSearch: (search: Record<string, unknown>): HighlightsSearch => ({
    search: (search.search as string | undefined) || undefined,
    tagId: (search.tagId as number | undefined) || undefined,
    labelId: (search.labelId as number | undefined) || undefined,
    highlightId: (search.highlightId as number | undefined) || undefined,
    from: parseDateSearchParam(search.from),
    to: parseDateSearchParam(search.to),
  }),
});
