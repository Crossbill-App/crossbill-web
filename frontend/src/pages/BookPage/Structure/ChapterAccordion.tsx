import type { ChapterWithHighlights, PositionResponse } from '@/api/generated/model';
import { ExpandMoreIcon, FlashcardsIcon, HighlightsIcon } from '@/theme/Icons.tsx';
import { Box, ButtonBase, Collapse, IconButton, Typography } from '@mui/material';
import { sumBy } from 'lodash';
import { useId, useState } from 'react';
import { ChapterReadIndicator } from './ChapterReadIndicator';

type ReadStatus = 'read' | 'current' | 'unread';

interface ChapterAccordionProps {
  chapter: ChapterWithHighlights;
  childrenByParentId: Map<number | null, ChapterWithHighlights[]>;
  gistByChapterId: Map<number, string>;
  bookId: number;
  depth?: number;
  readingPosition?: PositionResponse | null;
  /**
   * Ids of chapters on the current reading-position path, derived once from
   * unfiltered document order (see `StructurePage`). Membership, not sibling
   * position, is what decides "current" — a search filters and re-sorts
   * `childrenByParentId`, so peeking at the next rendered sibling would not
   * mean the next chapter in the book.
   */
  currentChapterIds: Set<number>;
  preExpanded?: boolean;
  onChapterClick?: (chapterId: number) => void;
}

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

interface ChapterRowProps {
  chapter: ChapterWithHighlights;
  gist?: string;
  depth: number;
  readStatus?: ReadStatus;
  onClick?: () => void;
  /** The expand toggle, for a chapter that has children. */
  expandControl?: React.ReactNode;
}

/**
 * One chapter in the tree, the same whether or not it has children.
 *
 * The row itself always opens the chapter — a parent has its own digest,
 * highlights and notes, so "has children" was never a reason to be unopenable.
 * Expanding is the separate chevron, which is the only control that touches the
 * children.
 */
const ChapterRow = ({
  chapter,
  gist,
  depth,
  readStatus,
  onClick,
  expandControl,
}: ChapterRowProps) => {
  const highlightCount = chapter.highlights.length;
  const flashcardCount = sumBy(chapter.highlights, (h) => h.flashcards.length);

  return (
    <Box
      sx={(theme) => ({
        ml: theme.spacing(depth * 2),
        borderBottom: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        '&:last-of-type': {
          borderBottom: depth > 0 ? 'none' : '1px solid',
          borderColor: 'divider',
        },
      })}
    >
      <ButtonBase
        onClick={onClick}
        sx={(theme) => ({
          flex: 1,
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
          py: theme.spacing(1),
          px: theme.spacing(2),
          minHeight: 48,
          textAlign: 'left',
          transition: 'background-color 0.2s ease',
          '@media (hover: hover)': {
            '&:hover': {
              bgcolor: 'action.hover',
            },
          },
        })}
      >
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, minWidth: 0 }}>
          {readStatus && <ChapterReadIndicator status={readStatus} chapterName={chapter.name} />}
          <Box sx={{ minWidth: 0 }}>
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
      {expandControl}
    </Box>
  );
};

export const ChapterAccordion = ({
  chapter,
  childrenByParentId,
  gistByChapterId,
  bookId,
  depth = 0,
  readingPosition,
  currentChapterIds,
  preExpanded = false,
  onChapterClick,
}: ChapterAccordionProps) => {
  const isRead =
    readingPosition != null &&
    chapter.start_position != null &&
    readingPosition.index >= chapter.start_position.index;
  const isCurrent = currentChapterIds.has(chapter.id);
  const readStatus: ReadStatus | undefined =
    readingPosition == null ? undefined : isCurrent ? 'current' : isRead ? 'read' : 'unread';
  const [expanded, setExpanded] = useState(isCurrent || readingPosition == null || preExpanded);
  const childrenId = useId();

  const childChapters = childrenByParentId.get(chapter.id) ?? [];
  const isLeaf = childChapters.length === 0;
  const gist = gistByChapterId.get(chapter.id);

  return (
    <Box data-chapter-read={isRead ? 'true' : 'false'}>
      <ChapterRow
        chapter={chapter}
        gist={gist}
        depth={depth}
        readStatus={readStatus}
        onClick={() => onChapterClick?.(chapter.id)}
        expandControl={
          isLeaf ? undefined : (
            <IconButton
              onClick={() => setExpanded(!expanded)}
              aria-label={`${expanded ? 'Collapse' : 'Expand'} ${chapter.name}`}
              aria-expanded={expanded}
              aria-controls={childrenId}
              sx={{
                mr: 1,
                transition: 'transform 0.2s ease',
                transform: expanded ? 'rotate(180deg)' : 'none',
              }}
            >
              <ExpandMoreIcon />
            </IconButton>
          )
        }
      />

      {!isLeaf && (
        <Collapse in={expanded} id={childrenId} unmountOnExit>
          {childChapters.map((child) => (
            <ChapterAccordion
              key={child.id}
              chapter={child}
              childrenByParentId={childrenByParentId}
              gistByChapterId={gistByChapterId}
              bookId={bookId}
              depth={depth + 1}
              readingPosition={readingPosition}
              currentChapterIds={currentChapterIds}
              preExpanded={preExpanded}
              onChapterClick={onChapterClick}
            />
          ))}
        </Collapse>
      )}
    </Box>
  );
};
