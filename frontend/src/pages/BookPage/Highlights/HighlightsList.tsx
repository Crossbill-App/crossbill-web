import type { Bookmark, Highlight } from '@/api/generated/model';
import { HighlightCard } from '@/components/cards/HighlightCard.tsx';
import { ChapterGroupedList } from '@/pages/BookPage/common/ChapterGroupedList.tsx';
import { Typography } from '@mui/material';
import type { ReactNode } from 'react';

export interface ChapterData {
  id: number;
  name: string;
  chapterNumber?: number;
  highlights: Highlight[];
}

interface ChapterListProps {
  chapters: ChapterData[];
  bookmarksByHighlightId: Record<number, Bookmark>;
  isLoading?: boolean;
  emptyState?: ReactNode;
  animationKey?: string;
  onOpenHighlight?: (highlightId: number) => void;
}

export const HighlightsList = ({
  chapters,
  bookmarksByHighlightId,
  isLoading,
  emptyState,
  animationKey = 'chapters',
  onOpenHighlight,
}: ChapterListProps) => (
  <ChapterGroupedList
    chapters={chapters}
    getChapterId={(chapter) => chapter.id}
    getChapterName={(chapter) => chapter.name}
    getItems={(chapter) => chapter.highlights}
    getItemKey={(highlight) => highlight.id}
    ariaLabel={(chapter) => `Highlights in ${chapter.name}`}
    isLoading={isLoading}
    emptyState={emptyState}
    animationKey={animationKey}
    cardListSx={{ gap: 2.5 }}
    renderItem={(highlight) => (
      <HighlightCard
        highlight={highlight}
        bookmark={bookmarksByHighlightId[highlight.id]}
        onOpenModal={onOpenHighlight}
      />
    )}
    renderEmptyChapter={() => (
      <Typography
        variant="body2"
        sx={{
          color: 'text.secondary',
          pl: 0.5,
        }}
      >
        No highlights found in this chapter.
      </Typography>
    )}
  />
);
