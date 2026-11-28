import { ReviewPage } from '@/pages/ReviewPage/ReviewPage';
import { createFileRoute } from '@tanstack/react-router';

export interface ReviewSearch {
  book?: number;
}

export const Route = createFileRoute('/review')({
  component: ReviewPage,
  validateSearch: (search: Record<string, unknown>): ReviewSearch => ({
    book: Number(search.book) || undefined,
  }),
});
