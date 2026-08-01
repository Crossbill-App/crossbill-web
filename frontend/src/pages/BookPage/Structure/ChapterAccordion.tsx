import type { ChapterWithHighlights, PositionResponse } from '@/api/generated/model';
import { ExpandMoreIcon, FlashcardsIcon, HighlightsIcon } from '@/theme/Icons.tsx';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  ButtonBase,
  Typography,
} from '@mui/material';
import { sumBy } from 'lodash';
import type { ReactNode } from 'react';
import { useState } from 'react';
import { ChapterReadIndicator } from './ChapterReadIndicator';

type ReadStatus = 'read' | 'current' | 'unread';

interface ChapterAccordionProps {
  chapter: ChapterWithHighlights;
  childrenByParentId: Map<number | null, ChapterWithHighlights[]>;
  gistByChapterId: Map<number, string>;
  bookId: number;
  depth?: number;
  isRead?: boolean;
  isCurrent?: boolean;
  readingPosition?: PositionResponse | null;
  preExpanded?: boolean;
  onChapterClick?: (chapterId: number) => void;
}

const accordionSx = (depth: number) => (theme: { spacing: (n: number) => string }) => ({
  boxShadow: 'none',
  '&:before': { display: 'none' },
  '&.Mui-expanded': { m: 0 },
  bgcolor: 'transparent',
  ml: theme.spacing(depth * 2),
  borderBottom: '1px solid',
  borderColor: 'divider',
  '&:last-of-type': {
    borderBottom: depth > 0 ? 'none' : '1px solid',
    borderRadius: 0,
    borderColor: 'divider',
  },
});

const GistLine = ({ gist }: { gist: string }) => (
  <Typography
    variant="body2"
    sx={{
      color: 'text.secondary',
      display: '-webkit-box',
      WebkitLineClamp: 2,
      WebkitBoxOrient: 'vertical',
      overflow: 'hidden',
    }}
  >
    {gist}
  </Typography>
);

const ExpandableChapter = ({
  name,
  gist,
  depth,
  expanded,
  onToggle,
  readStatus,
  children,
}: {
  name: string;
  gist?: string;
  depth: number;
  expanded: boolean;
  onToggle: () => void;
  readStatus?: ReadStatus;
  children: ReactNode;
}) => (
  <Accordion expanded={expanded} onChange={onToggle} sx={accordionSx(depth)}>
    <AccordionSummary
      expandIcon={<ExpandMoreIcon />}
      sx={{
        borderRadius: 0,
        '&.Mui-expanded': { minHeight: 48 },
        '& .MuiAccordionSummary-content.Mui-expanded': { my: '12px' },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        {readStatus && <ChapterReadIndicator status={readStatus} />}
        <Box>
          <Typography variant="body1" sx={{ fontWeight: 600 }}>
            {name}
          </Typography>
          {gist && <GistLine gist={gist} />}
        </Box>
      </Box>
    </AccordionSummary>
    <AccordionDetails sx={{ pt: 0 }}>{children}</AccordionDetails>
  </Accordion>
);

const LeafChapterRow = ({
  chapter,
  gist,
  depth,
  readStatus,
  onClick,
}: {
  chapter: ChapterWithHighlights;
  gist?: string;
  depth: number;
  readStatus?: ReadStatus;
  onClick?: () => void;
}) => {
  const highlightCount = chapter.highlights.length;
  const flashcardCount = sumBy(chapter.highlights, (h) => h.flashcards.length);

  return (
    <ButtonBase
      onClick={onClick}
      sx={(theme) => ({
        ml: theme.spacing(depth * 2),
        borderBottom: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        py: theme.spacing(1),
        px: theme.spacing(2),
        minHeight: 48,
        width: '100%',
        textAlign: 'left',
        transition: 'background-color 0.2s ease',
        '@media (hover: hover)': {
          '&:hover': {
            bgcolor: 'action.hover',
          },
        },
        '&:last-of-type': {
          borderBottom: depth > 0 ? 'none' : '1px solid',
          borderColor: 'divider',
        },
      })}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        {readStatus && <ChapterReadIndicator status={readStatus} />}
        <Box>
          <Typography variant="body1" sx={{ fontWeight: 600 }}>
            {chapter.name}
          </Typography>
          {gist && <GistLine gist={gist} />}
        </Box>
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, color: 'text.secondary' }}>
        {highlightCount > 0 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <HighlightsIcon sx={{ fontSize: 16 }} />
            <Typography variant="caption">{highlightCount}</Typography>
          </Box>
        )}
        {flashcardCount > 0 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <FlashcardsIcon sx={{ fontSize: 16 }} />
            <Typography variant="caption">{flashcardCount}</Typography>
          </Box>
        )}
      </Box>
    </ButtonBase>
  );
};

export const ChapterAccordion = ({
  chapter,
  childrenByParentId,
  gistByChapterId,
  bookId,
  depth = 0,
  isRead,
  isCurrent,
  readingPosition,
  preExpanded = false,
  onChapterClick,
}: ChapterAccordionProps) => {
  const readStatus: ReadStatus | undefined =
    readingPosition == null ? undefined : isCurrent ? 'current' : isRead ? 'read' : 'unread';
  const [expanded, setExpanded] = useState(isCurrent || readingPosition == null || preExpanded);

  const childChapters = childrenByParentId.get(chapter.id) ?? [];
  const isLeaf = childChapters.length === 0;
  const gist = gistByChapterId.get(chapter.id);

  let content: ReactNode;
  if (!isLeaf) {
    content = (
      <ExpandableChapter
        name={chapter.name}
        gist={gist}
        depth={depth}
        expanded={expanded}
        onToggle={() => setExpanded(!expanded)}
        readStatus={readStatus}
      >
        <Box>
          {childChapters.map((child, index) => {
            const childIsRead =
              readingPosition != null && child.start_position != null
                ? readingPosition.index >= child.start_position.index
                : undefined;
            // Current = this child is read but the next sibling is not
            const isLastChild = index === childChapters.length - 1;
            const nextIsRead = isLastChild
              ? false
              : readingPosition != null && childChapters[index + 1].start_position != null
                ? readingPosition.index >= childChapters[index + 1].start_position!.index
                : false;
            const childIsCurrent = isCurrent === true && childIsRead === true && !nextIsRead;

            return (
              <ChapterAccordion
                key={child.id}
                chapter={child}
                childrenByParentId={childrenByParentId}
                gistByChapterId={gistByChapterId}
                bookId={bookId}
                depth={depth + 1}
                isRead={childIsRead}
                isCurrent={childIsCurrent}
                readingPosition={readingPosition}
                onChapterClick={onChapterClick}
              />
            );
          })}
        </Box>
      </ExpandableChapter>
    );
  } else {
    content = (
      <LeafChapterRow
        chapter={chapter}
        gist={gist}
        depth={depth}
        readStatus={readStatus}
        onClick={() => onChapterClick?.(chapter.id)}
      />
    );
  }

  return <Box data-chapter-read={isRead ? 'true' : 'false'}>{content}</Box>;
};
