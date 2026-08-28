import type { Bookmark, Highlight } from '@/api/generated/model';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { TagChipList } from '@/components/TagChipList.tsx';
import { formatHighlightDate } from '@/pages/BookPage/common/highlightDates.ts';
import { LabelIndicator } from '@/pages/BookPage/common/LabelIndicator.tsx';
import { NotOnDeviceChip } from '@/pages/BookPage/common/NotOnDeviceChip.tsx';
import {
  BookmarkFilledIcon,
  DateIcon,
  FlashcardsIcon,
  HighlightsIcon,
  NotesIcon,
} from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { countLabel } from '@/utils/counts.ts';
import type { SvgIconComponent } from '@mui/icons-material';
import { Box, Typography } from '@mui/material';

export interface HighlightCardProps {
  highlight: Highlight;
  bookmark?: Bookmark;
  /** Notes linked to this highlight. Not on the payload — see `useNoteCountsByHighlight`. */
  noteCount?: number;
  onOpenModal?: (highlightId: number) => void;
}

interface FooterProps {
  highlight: Highlight;
  bookmark?: Bookmark;
  noteCount: number;
}

/** An icon and a number. `role="img"` carries the unit the glyph alone implies. */
const CountBadge = ({
  icon: Icon,
  count,
  noun,
}: {
  icon: SvgIconComponent;
  count: number;
  noun: string;
}) => (
  <Box component="span" role="img" aria-label={countLabel(count, noun)}>
    <Icon sx={{ fontSize: ICON_SIZE.inline, verticalAlign: 'middle', ml: 1, mt: -0.5 }} />
    <span>&nbsp;&nbsp;{count}</span>
  </Box>
);

const Footer = ({ highlight, bookmark, noteCount }: FooterProps) => {
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
        <DateIcon sx={{ fontSize: ICON_SIZE.inline, color: 'text.secondary' }} />
        <MetadataRow
          variant="caption"
          items={[
            formatHighlightDate(highlight.datetime),
            highlight.page && `Page ${highlight.page}`,
            hasBookmark && (
              <BookmarkFilledIcon
                sx={{ fontSize: ICON_SIZE.inline, verticalAlign: 'middle', ml: 1, mt: -0.5 }}
              />
            ),
            !!noteCount && <CountBadge icon={NotesIcon} count={noteCount} noun="note" />,
            !!highlight.flashcards.length && (
              <CountBadge
                icon={FlashcardsIcon}
                count={highlight.flashcards.length}
                noun="flashcard"
              />
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

export const HighlightCard = ({
  highlight,
  bookmark,
  noteCount = 0,
  onOpenModal,
}: HighlightCardProps) => {
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
          <HighlightsIcon
            sx={{
              fontSize: ICON_SIZE.prominent,
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

        <Footer highlight={highlight} bookmark={bookmark} noteCount={noteCount} />
      </Box>
    </HoverableCardActionArea>
  );
};
