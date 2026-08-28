import type { ChapterWithHighlights, PositionResponse } from '@/api/generated/model';
import { CollapseChevron } from '@/components/CollapseChevron.tsx';
import { FlashcardsIcon, HighlightsIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, ButtonBase, Collapse, IconButton, Typography, type Theme } from '@mui/material';
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

const ChapterLabel = ({
  chapter,
  gist,
  readStatus,
}: {
  chapter: ChapterWithHighlights;
  gist?: string;
  readStatus?: ReadStatus;
}) => (
  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, minWidth: 0 }}>
    {readStatus && <ChapterReadIndicator status={readStatus} chapterName={chapter.name} />}
    <Box sx={{ minWidth: 0, textAlign: 'left' }}>
      <Typography variant="body1" sx={{ fontWeight: 600 }}>
        {chapter.name}
      </Typography>
      {gist && <GistLine gist={gist} />}
    </Box>
  </Box>
);

const ChapterCounts = ({ chapter }: { chapter: ChapterWithHighlights }) => {
  const highlightCount = chapter.highlights.length;
  const flashcardCount = sumBy(chapter.highlights, (h) => h.flashcards.length);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, color: 'text.secondary' }}>
      {highlightCount > 0 && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <HighlightsIcon sx={{ fontSize: ICON_SIZE.inline }} />
          <Typography variant="caption">{highlightCount}</Typography>
        </Box>
      )}
      {flashcardCount > 0 && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <FlashcardsIcon sx={{ fontSize: ICON_SIZE.inline }} />
          <Typography variant="caption">{flashcardCount}</Typography>
        </Box>
      )}
    </Box>
  );
};

const rowSx = (depth: number) => (theme: Theme) => ({
  ml: theme.spacing(depth * 2),
  borderBottom: '1px solid',
  borderColor: 'divider',
  display: 'flex',
  alignItems: 'center',
  '&:last-of-type': {
    borderBottom: depth > 0 ? 'none' : '1px solid',
    borderColor: 'divider',
  },
});

/** Shared geometry, so a parent row and a leaf row are the same height. */
const rowBodySx = (theme: Theme) => ({
  flex: 1,
  minWidth: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 1,
  py: theme.spacing(1),
  px: theme.spacing(2),
  minHeight: 48,
});

const hoverSx = {
  transition: 'background-color 0.2s ease',
  '@media (hover: hover)': {
    '&:hover': { bgcolor: 'action.hover' },
  },
};

interface ChapterRowProps {
  chapter: ChapterWithHighlights;
  gist?: string;
  depth: number;
  readStatus?: ReadStatus;
  onOpen: () => void;
}

/** A chapter with no children: the whole row opens it, nothing competes. */
const LeafChapterRow = ({ chapter, gist, depth, readStatus, onOpen }: ChapterRowProps) => (
  <Box sx={rowSx(depth)}>
    <ButtonBase onClick={onOpen} sx={[rowBodySx, hoverSx]}>
      <ChapterLabel chapter={chapter} gist={gist} readStatus={readStatus} />
      <ChapterCounts chapter={chapter} />
    </ButtonBase>
  </Box>
);

interface ParentChapterRowProps extends ChapterRowProps {
  expanded: boolean;
  onToggle: () => void;
  childrenId: string;
}

/**
 * A chapter with children, which has two things to offer and so splits the row
 * between them: the title opens the chapter, everything else works the
 * children list. Both actions have their own focusable control — the title and
 * the chevron — and the row's own handler is a mouse convenience on top of
 * them, which is why it sits on a plain container rather than a button.
 */
const ParentChapterRow = ({
  chapter,
  gist,
  depth,
  readStatus,
  onOpen,
  expanded,
  onToggle,
  childrenId,
}: ParentChapterRowProps) => (
  <Box sx={[rowSx(depth), { cursor: 'pointer' }]} onClick={onToggle}>
    <Box sx={rowBodySx}>
      <ButtonBase
        onClick={(event) => {
          event.stopPropagation();
          onOpen();
        }}
        sx={[{ borderRadius: 1, mx: -0.5, px: 0.5, minWidth: 0 }, hoverSx]}
      >
        <ChapterLabel chapter={chapter} gist={gist} readStatus={readStatus} />
      </ButtonBase>
      <ChapterCounts chapter={chapter} />
    </Box>
    <IconButton
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      aria-label={`${expanded ? 'Collapse' : 'Expand'} ${chapter.name}`}
      aria-expanded={expanded}
      aria-controls={childrenId}
      sx={{ mr: 1 }}
    >
      <CollapseChevron isExpanded={expanded} />
    </IconButton>
  </Box>
);

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
      {isLeaf ? (
        <LeafChapterRow
          chapter={chapter}
          gist={gist}
          depth={depth}
          readStatus={readStatus}
          onOpen={() => onChapterClick?.(chapter.id)}
        />
      ) : (
        <ParentChapterRow
          chapter={chapter}
          gist={gist}
          depth={depth}
          readStatus={readStatus}
          onOpen={() => onChapterClick?.(chapter.id)}
          expanded={expanded}
          onToggle={() => setExpanded(!expanded)}
          childrenId={childrenId}
        />
      )}

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
