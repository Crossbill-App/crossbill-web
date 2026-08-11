import { Carousel } from '@/components/carousel/Carousel.tsx';
import { CarouselItem } from '@/components/carousel/CarouselItem.tsx';
import { RelatedContentCard } from '@/components/search/RelatedContentCard.tsx';
import type { GlobalSearchRow } from '@/components/search/globalSearchRows.ts';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Box } from '@mui/material';

interface RelatedContentSectionProps {
  title: string;
  rows: GlobalSearchRow[];
}

/**
 * Trailing strip of semantically related content for a tab.
 *
 * Renders nothing when there is nothing to relate — the feature being off, the
 * anchor not being embedded yet and every match scoring below the floor all
 * arrive here as an empty list, and none of them is worth a heading over an
 * empty row.
 */
export const RelatedContentSection = ({ title, rows }: RelatedContentSectionProps) => {
  if (rows.length === 0) return null;

  return (
    <Box
      sx={{ mt: 4, gap: 2, display: 'flex', flexDirection: 'column' }}
      onTouchStart={(e) => e.stopPropagation()}
      onTouchMove={(e) => e.stopPropagation()}
      onTouchEnd={(e) => e.stopPropagation()}
    >
      <SectionTitle component="h3">{title}</SectionTitle>
      <Carousel aria-label={title}>
        {rows.map((row) => (
          <CarouselItem key={row.key}>
            <RelatedContentCard row={row} />
          </CarouselItem>
        ))}
      </Carousel>
    </Box>
  );
};
