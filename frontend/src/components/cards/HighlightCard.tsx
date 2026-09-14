import type { Bookmark, Highlight } from '@/api/generated/model';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { CountWithIcon } from '@/components/CountWithIcon.tsx';
import { OpenInReaderButton } from '@/components/reader/OpenInReaderButton.tsx';
import { TagChipList } from '@/components/TagChipList.tsx';
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
import { formatDate } from '@/utils/date.ts';
import { buildPreviewText } from '@/utils/highlightPreview.ts';
import { Box, Typography } from '@mui/material';
import { memo, useMemo } from 'react';

// Kept whether or not the reader action renders, so previews wrap the same everywhere.
const CORNER_ACTION_GUTTER = 6.5;

const readerActionSx = {
  position: 'absolute',
  top: 8,
  right: 8,
  color: 'text.secondary',
  '& svg': { fontSize: ICON_SIZE.ui },
} as const;

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
            formatDate(highlight.datetime),
            highlight.page && `Page ${highlight.page}`,
            hasBookmark && (
              <BookmarkFilledIcon
                sx={{ fontSize: ICON_SIZE.inline, verticalAlign: 'middle', ml: 1, mt: -0.5 }}
              />
            ),
            !!noteCount && <CountWithIcon icon={NotesIcon} count={noteCount} noun="note" />,
            !!highlight.flashcards.length && (
              <CountWithIcon
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

/**
 * One highlight in a list, opening the highlight dialog when clicked.
 *
 * Memoised because the highlights tab renders its whole set at once
 * (ADR-0003), so a book's worth of these re-render on every filter keystroke,
 * sort toggle and dialog open. That only pays off while all four props stay
 * referentially stable — `onOpenModal` in particular must be a `useCallback`,
 * never an inline arrow, or the memo silently does nothing.
 */
export const HighlightCard = memo(function HighlightCard({
  highlight,
  bookmark,
  noteCount = 0,
  onOpenModal,
}: HighlightCardProps) {
  const previewText = useMemo(() => buildPreviewText(highlight.text), [highlight.text]);

  const handleOpenModal = () => {
    onOpenModal?.(highlight.id);
  };

  return (
    // The card is a button, and a link inside a button is invalid HTML.
    <Box sx={{ position: 'relative' }}>
      <HoverableCardActionArea
        id={`highlight-${highlight.id}`}
        onClick={handleOpenModal}
        sx={{
          py: 3.5,
          pl: 2.5,
          pr: CORNER_ACTION_GUTTER,
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

      <OpenInReaderButton
        bookId={highlight.book_id}
        highlightId={highlight.id}
        size="small"
        sx={readerActionSx}
      />
    </Box>
  );
});
