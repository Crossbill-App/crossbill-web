import type { BookWithHighlightCount } from '@/api/generated/model';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { Carousel } from '@/components/carousel/Carousel.tsx';
import { CarouselItem } from '@/components/carousel/CarouselItem.tsx';
import { PAGE_GUTTER } from '@/components/layout/Layouts.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Alert, Box } from '@mui/material';
import { BookCard } from './BookCard';

/**
 * Matches the all-books grid from sm up; tighter on phones, where a 32px gap
 * would cost the row its second cover.
 */
const CAROUSEL_GAP = { xs: 2, sm: 4 };

export interface BookCarouselSectionProps {
  title: string;
  ariaLabel: string;
  books: BookWithHighlightCount[] | undefined;
  isLoading: boolean;
  isError: boolean;
  errorText: string;
}

/**
 * One titled row of book covers on the landing page. Each caller owns its own
 * query and passes the outcome in; what a row means is the caller's business,
 * and how a row looks is this component's.
 */
export const BookCarouselSection = ({
  title,
  ariaLabel,
  books,
  isLoading,
  isError,
  errorText,
}: BookCarouselSectionProps) => {
  // Don't render the section at all when the query came back with no books
  if (!isLoading && !isError && (!books || books.length === 0)) {
    return null;
  }

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>{title}</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">{errorText}</Alert>
        </Box>
      )}

      {books && books.length > 0 && (
        <Carousel aria-label={ariaLabel} gap={CAROUSEL_GAP} bleed={PAGE_GUTTER}>
          {books.map((book) => (
            <CarouselItem key={book.id}>
              <BookCard book={book} />
            </CarouselItem>
          ))}
        </Carousel>
      )}
    </Box>
  );
};
