import type { Bookmark, ChapterWithHighlights, TagInBook } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { HighlightCard } from '@/components/cards/HighlightCard.tsx';
import { HighlightViewDialog } from '@/pages/BookPage/Highlights/HighlightViewDialog/HighlightViewDialog.tsx';
import { useHighlightDialog } from '@/pages/BookPage/Highlights/hooks/useHighlightDialog.ts';

interface HighlightsSectionProps {
  chapter: ChapterWithHighlights;
  bookId: number;
  bookmarksByHighlightId: Record<number, Bookmark>;
  availableTags: TagInBook[];
}

export const HighlightsSection = ({
  chapter,
  bookId,
  bookmarksByHighlightId,
  availableTags,
}: HighlightsSectionProps) => {
  const highlights = chapter.highlights;

  const highlightDialog = useHighlightDialog({
    allHighlights: highlights,
    isMobile: false,
    syncToUrl: false,
  });

  if (highlights.length === 0) {
    return <EmptyStateText>No highlights in this chapter yet.</EmptyStateText>;
  }

  return (
    <>
      <CardList>
        {highlights.map((highlight) => (
          <li key={highlight.id}>
            <HighlightCard
              highlight={highlight}
              bookmark={bookmarksByHighlightId[highlight.id]}
              onOpenModal={highlightDialog.open}
            />
          </li>
        ))}
      </CardList>

      {highlightDialog.activeItem && (
        <HighlightViewDialog
          controller={highlightDialog}
          bookId={bookId}
          availableTags={availableTags}
          bookmarksByHighlightId={bookmarksByHighlightId}
        />
      )}
    </>
  );
};
