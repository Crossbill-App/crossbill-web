import type { RecentCapture } from '@/api/generated/model';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { LabelIndicator } from '@/pages/BookPage/common/LabelIndicator.tsx';
import { NoteKindChip } from '@/pages/BookPage/Notes/NoteKindChip';
import { HighlightsIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { markdownStyles } from '@/theme/theme';
import { clampToLines } from '@/utils/clampToLines.ts';
import { formatTime } from '@/utils/date.ts';
import { buildPreviewText } from '@/utils/highlightPreview.ts';
import { Box, Link, Typography, useTheme } from '@mui/material';
import { createLink } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';

import { captureLinkProps, moreInBookLinkProps } from './captureLinks.ts';

/** See `GlobalSearchResultRow`: MUI's own `component={Link}` drops the search params. */
const LinkCardActionArea = createLink(HoverableCardActionArea);
const RouterLink = createLink(Link);

interface CaptureEntryProps {
  capture: RecentCapture;
}

/**
 * One highlight or note in the dashboard's feed.
 *
 * A highlight is marked by the quote glyph, as on the book page; a note by
 * its title and kind chip.
 */
export const CaptureEntry = ({ capture }: CaptureEntryProps) => {
  const { t } = useTranslation();
  const theme = useTheme();
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

        {/* Baseline-aligned with the time, so the time reads level with the first line. */}
        <Box sx={{ flex: 1, minWidth: 0, alignSelf: 'baseline' }}>
          {/* An h4: the day this capture sits under is the h3 above it. */}
          {capture.title && (
            <Typography variant="h3" component="h4">
              {capture.title}
            </Typography>
          )}

          {capture.text &&
            (isHighlight ? (
              <Typography variant="body1">{buildPreviewText(capture.text)}</Typography>
            ) : (
              // Markdown, as `NoteCard` renders the same body.
              <Box sx={{ ...markdownStyles(theme), ...clampToLines(2) }}>
                <ReactMarkdown>{capture.text}</ReactMarkdown>
              </Box>
            ))}

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
            <LabelIndicator label={capture.label} />
            <NoteKindChip kind={capture.note_kind} />
            <MetadataRow
              variant="caption"
              items={[
                capture.book_title,
                capture.chapter_name,
                capture.page && t('common.labels.page', { page: capture.page }),
              ]}
            />
          </Box>
        </Box>

        <Typography
          variant="caption"
          sx={{ color: 'text.secondary', whiteSpace: 'nowrap', alignSelf: 'baseline' }}
        >
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
          {t('landing.captureEntry.moreInBook', {
            count: capture.more_in_book,
            book: capture.book_title,
          })}
        </RouterLink>
      )}
    </Box>
  );
};
