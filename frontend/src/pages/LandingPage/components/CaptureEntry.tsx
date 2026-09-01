import type { RecentCapture } from '@/api/generated/model';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { LabelIndicator } from '@/pages/BookPage/common/LabelIndicator.tsx';
import { NoteKindChip } from '@/pages/BookPage/Notes/NoteKindChip';
import { HighlightsIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { formatTime } from '@/utils/date.ts';
import { buildPreviewText } from '@/utils/highlightPreview.ts';
import { Box, Link, Typography } from '@mui/material';
import { createLink } from '@tanstack/react-router';

import { captureLinkProps, moreInBookLinkProps } from './captureLinks.ts';

/** See `GlobalSearchResultRow`: MUI's own `component={Link}` drops the search params. */
const LinkCardActionArea = createLink(HoverableCardActionArea);
const RouterLink = createLink(Link);

/** A note's body, clamped rather than truncated in JS: it is markdown, and a word cap would cut a fence. */
const clampToTwoLines = {
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical' as const,
  overflow: 'hidden',
};

interface CaptureEntryProps {
  capture: RecentCapture;
}

/**
 * One highlight or note in the dashboard's feed.
 *
 * A highlight is marked by the quote glyph and a note by the rail down its
 * left, which is how the book page marks each of them: the reader learns the
 * two markers once.
 */
export const CaptureEntry = ({ capture }: CaptureEntryProps) => {
  const isHighlight = capture.kind === 'highlight';

  return (
    <Box>
      <LinkCardActionArea
        {...captureLinkProps(capture)}
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1.5,
          textAlign: 'left',
          py: 1.5,
          px: 1.5,
          ...(isHighlight ? {} : { borderLeft: '3px solid', borderColor: 'primary.main', pl: 2 }),
        }}
      >
        {isHighlight && (
          <HighlightsIcon
            sx={{
              fontSize: ICON_SIZE.prominent,
              color: 'primary.main',
              flexShrink: 0,
              mt: 0.3,
              opacity: 0.7,
            }}
          />
        )}

        <Box sx={{ flex: 1, minWidth: 0 }}>
          {capture.title && <Typography variant="h3">{capture.title}</Typography>}

          {capture.text && (
            <Typography variant="body1" sx={isHighlight ? undefined : clampToTwoLines}>
              {isHighlight ? buildPreviewText(capture.text) : capture.text}
            </Typography>
          )}

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
            <LabelIndicator label={capture.label} />
            <NoteKindChip kind={capture.note_kind} />
            <MetadataRow
              variant="caption"
              items={[
                capture.book_title,
                capture.chapter_name,
                capture.page && `Page ${capture.page}`,
              ]}
            />
          </Box>
        </Box>

        <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
          {formatTime(capture.captured_at)}
        </Typography>
      </LinkCardActionArea>

      {capture.more_in_book > 0 && (
        <RouterLink
          {...moreInBookLinkProps(capture)}
          sx={{
            display: 'inline-block',
            ml: isHighlight ? 5.5 : 2,
            mb: 1,
            color: 'text.secondary',
            fontSize: '0.8rem',
            textDecoration: 'none',
            '&:hover': { textDecoration: 'underline' },
          }}
        >
          {`+${capture.more_in_book} more in ${capture.book_title} that day`}
        </RouterLink>
      )}
    </Box>
  );
};
