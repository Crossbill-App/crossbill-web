import type { Bookmark, Highlight } from '@/api/generated/model';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { TagChipList } from '@/components/TagChipList.tsx';
import { formatHighlightDate } from '@/pages/BookPage/common/highlightDates.ts';
import { LabelIndicator } from '@/pages/BookPage/common/LabelIndicator.tsx';
import { NotOnDeviceChip } from '@/pages/BookPage/common/NotOnDeviceChip.tsx';
import { BookmarkFilledIcon, DateIcon, FlashcardsIcon, QuoteIcon } from '@/theme/Icons.tsx';
import { Box, Typography } from '@mui/material';

export interface HighlightCardProps {
  highlight: Highlight;
  bookmark?: Bookmark;
  onOpenModal?: (highlightId: number) => void;
}

interface FooterProps {
  highlight: Highlight;
  bookmark?: Bookmark;
}

const Footer = ({ highlight, bookmark }: FooterProps) => {
  const hasBookmark = !!bookmark;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', sm: 'row' },
        gap: 2,
        mt: 1,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          pl: 4.5,
        }}
      >
        <LabelIndicator label={highlight.label} size="small" />
        <NotOnDeviceChip removed={highlight.removed_from_devices} />
        <DateIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
        <MetadataRow
          variant="caption"
          items={[
            formatHighlightDate(highlight.datetime),
            highlight.page && `Page ${highlight.page}`,
            hasBookmark && (
              <BookmarkFilledIcon sx={{ fontSize: 16, verticalAlign: 'middle', ml: 1, mt: -0.5 }} />
            ),
            !!highlight.flashcards.length && (
              <>
                <FlashcardsIcon sx={{ fontSize: 16, verticalAlign: 'middle', ml: 1, mt: -0.5 }} />
                <span>&nbsp;&nbsp;{highlight.flashcards.length}</span>
              </>
            ),
          ]}
        />
      </Box>

      <Box>
        <TagChipList tags={highlight.tags} />
      </Box>
    </Box>
  );
};

const previewWordCount = 40;

export const HighlightCard = ({ highlight, bookmark, onOpenModal }: HighlightCardProps) => {
  const startsWithLowercase =
    highlight.text.length > 0 &&
    highlight.text[0] === highlight.text[0].toLowerCase() &&
    highlight.text[0] !== highlight.text[0].toUpperCase();
  const formattedText = startsWithLowercase ? `...${highlight.text}` : highlight.text;

  const words = formattedText.split(/\s+/);
  const shouldTruncate = words.length > previewWordCount;

  const previewText = shouldTruncate
    ? words.slice(0, previewWordCount).join(' ') + '...'
    : formattedText;

  const handleOpenModal = () => {
    onOpenModal?.(highlight.id);
  };

  return (
    <HoverableCardActionArea
      id={`highlight-${highlight.id}`}
      onClick={handleOpenModal}
      sx={{
        py: 3.5,
        px: 2.5,
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'start', gap: 1.5, mb: 2 }}>
          <QuoteIcon
            sx={{
              fontSize: 22,
              color: 'primary.main',
              flexShrink: 0,
              mt: 0.3,
              opacity: 0.7,
            }}
          />
          <Typography
            variant="body1"
            sx={{
              color: 'text.primary',
            }}
          >
            {previewText}
          </Typography>
        </Box>

        <Footer highlight={highlight} bookmark={bookmark} />
      </Box>
    </HoverableCardActionArea>
  );
};
