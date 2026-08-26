import type { Highlight } from '@/api/generated/model';
import { LabelIndicator } from '@/pages/BookPage/common/LabelIndicator.tsx';
import { NotOnDeviceChip } from '@/pages/BookPage/common/NotOnDeviceChip.tsx';
import { formatHighlightDate } from '@/pages/BookPage/common/highlightDates.ts';
import { DateIcon, QuoteIcon } from '@/theme/Icons.tsx';
import { Box, Typography } from '@mui/material';

interface HighlightContentProps {
  highlight: Highlight;
  onLabelClick?: (event: React.MouseEvent<HTMLElement>) => void;
}

export const HighlightContent = ({ highlight, onLabelClick }: HighlightContentProps) => {
  const startsWithLowercase =
    highlight.text.length > 0 &&
    highlight.text[0] === highlight.text[0].toLowerCase() &&
    highlight.text[0] !== highlight.text[0].toUpperCase();

  const renderHighlightText = () => {
    const prefix = startsWithLowercase ? '...' : '';
    // Split by newlines and filter out empty strings
    const paragraphs = highlight.text.split('\n').filter((p) => p.trim() !== '');

    return (
      <>
        {paragraphs.map((paragraph, index) => (
          <Typography
            key={index}
            component="p"
            variant="h6"
            sx={{
              fontWeight: 500,
              color: 'text.primary',
              lineHeight: 1.7,
              margin: 0,
              marginBottom: index < paragraphs.length - 1 ? 2 : 0,
            }}
          >
            {index === 0 ? prefix + paragraph : paragraph}
          </Typography>
        ))}
      </>
    );
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        flex: 1,
      }}
    >
      {/* Highlight Text */}
      <Box sx={{ display: 'flex', alignItems: 'start', gap: 2 }}>
        <QuoteIcon
          sx={{
            fontSize: 28,
            color: 'primary.main',
            flexShrink: 0,
            mt: 0.5,
            opacity: 0.7,
          }}
        />
        <Box sx={{ flex: 1 }}>{renderHighlightText()}</Box>
      </Box>

      {/* Metadata */}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', opacity: 0.8 }}>
        <DateIcon
          sx={{
            fontSize: 20,
            color: 'text.secondary',
          }}
        />
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
          }}
        >
          {formatHighlightDate(highlight.datetime)}
          {highlight.page && ` • Page ${highlight.page}`}
        </Typography>
        <LabelIndicator label={highlight.label} onClick={onLabelClick} size="medium" />
        <NotOnDeviceChip removed={highlight.removed_from_devices} size="medium" />
      </Box>
    </Box>
  );
};
