import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Box, Typography, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

interface ChapterGroupedListProps<TChapter, TItem> {
  chapters: TChapter[];
  getChapterId: (chapter: TChapter) => number;
  getChapterName: (chapter: TChapter) => string;
  getItems: (chapter: TChapter) => TItem[];
  getItemKey: (item: TItem) => number | string;
  renderItem: (item: TItem) => ReactNode;
  /** Builds the CardList aria-label. Takes the chapter, not just its name, so
   *  a group that is not a chapter can name itself differently. */
  ariaLabel: (chapter: TChapter) => string;
  isLoading?: boolean;
  /** Shown in place of the list when there is no chapter to show. */
  emptyState?: ReactNode;
  animationKey?: string;
  /** Extra styles merged onto each chapter's CardList. */
  cardListSx?: SxProps<Theme>;
  /** Rendered in place of the card list when a chapter has no items. */
  renderEmptyChapter?: () => ReactNode;
}

/**
 * Generic chapter-grouped list: an optional "Searching..." loading state, a
 * fade-in wrapper, an empty-state branch, then a `SectionTitle` + `CardList`
 * per chapter. Shared by the highlights and flashcards tabs, which differ only
 * in the item card and a couple of presentational knobs.
 */
export const ChapterGroupedList = <TChapter, TItem>({
  chapters,
  getChapterId,
  getChapterName,
  getItems,
  getItemKey,
  renderItem,
  ariaLabel,
  isLoading,
  emptyState = <EmptyStateText>No chapters found.</EmptyStateText>,
  animationKey = 'chapters',
  cardListSx,
  renderEmptyChapter,
}: ChapterGroupedListProps<TChapter, TItem>) => {
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
          }}
        >
          Searching...
        </Typography>
      </Box>
    );
  }

  return (
    <FadeInOut ekey={animationKey}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {chapters.length === 0
          ? emptyState
          : chapters.map((chapter) => {
              const chapterId = getChapterId(chapter);
              const chapterName = getChapterName(chapter);
              const items = getItems(chapter);

              return (
                <Box key={chapterId} id={`chapter-${chapterId}`}>
                  <SectionTitle showDivider>{chapterName}</SectionTitle>

                  {items.length === 0 && renderEmptyChapter ? (
                    renderEmptyChapter()
                  ) : (
                    <CardList sx={cardListSx} aria-label={ariaLabel(chapter)}>
                      {items.map((item) => (
                        <li key={getItemKey(item)}>{renderItem(item)}</li>
                      ))}
                    </CardList>
                  )}
                </Box>
              );
            })}
      </Box>
    </FadeInOut>
  );
};
