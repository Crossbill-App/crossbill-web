import type { Bookmark, Highlight } from '@/api/generated/model';
import { HighlightCard } from '@/components/cards/HighlightCard.tsx';
import { ChapterGroupedList } from '@/pages/BookPage/common/ChapterGroupedList.tsx';
import { Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

export interface ChapterData {
  id: number;
  name: string;
  chapterNumber?: number;
  highlights: Highlight[];
}

interface ChapterListProps {
  chapters: ChapterData[];
  bookmarksByHighlightId: Record<number, Bookmark>;
  noteCountByHighlightId: Record<number, number>;
  isLoading?: boolean;
  emptyState?: ReactNode;
  onOpenHighlight?: (highlightId: number) => void;
}

export const HighlightsList = ({
  chapters,
  bookmarksByHighlightId,
  noteCountByHighlightId,
  isLoading,
  emptyState,
  onOpenHighlight,
}: ChapterListProps) => {
  const { t } = useTranslation();
  return (
    <ChapterGroupedList
      chapters={chapters}
      getChapterId={(chapter) => chapter.id}
      getChapterName={(chapter) => chapter.name}
      getItems={(chapter) => chapter.highlights}
      getItemKey={(highlight) => highlight.id}
      ariaLabel={(chapter) => t('highlights.list.chapterAriaLabel', { chapter: chapter.name })}
      isLoading={isLoading}
      emptyState={emptyState}
      cardListSx={{ gap: 1, mb: 4 }}
      renderItem={(highlight) => (
        <HighlightCard
          highlight={highlight}
          bookmark={bookmarksByHighlightId[highlight.id]}
          noteCount={noteCountByHighlightId[highlight.id]}
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
          {t('highlights.list.emptyChapter')}
        </Typography>
      )}
    />
  );
};
