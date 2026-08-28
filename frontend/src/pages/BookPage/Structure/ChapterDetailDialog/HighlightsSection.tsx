import type {
  Bookmark,
  ChapterWithHighlights,
  HighlightSearchItem,
  TagInBook,
} from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { HighlightCard } from '@/components/cards/HighlightCard.tsx';
import { RelatedContentSection } from '@/components/search/RelatedContentSection.tsx';
import { highlightRows } from '@/components/search/globalSearchRows.ts';
import { HighlightViewDialog } from '@/pages/BookPage/Highlights/HighlightViewDialog/HighlightViewDialog.tsx';
import { useHighlightDialog } from '@/pages/BookPage/Highlights/hooks/useHighlightDialog.ts';
import { useNoteCountsByHighlight } from '@/pages/BookPage/Notes/hooks/useNoteCountsByHighlight.ts';

interface HighlightsSectionProps {
  chapter: ChapterWithHighlights;
  bookId: number;
  relatedContent: HighlightSearchItem[];
  bookmarksByHighlightId: Record<number, Bookmark>;
  availableTags: TagInBook[];
}

export const HighlightsSection = ({
  chapter,
  bookId,
  bookmarksByHighlightId,
  relatedContent,
  availableTags,
}: HighlightsSectionProps) => {
  const highlights = chapter.highlights;
  const noteCountByHighlightId = useNoteCountsByHighlight();

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
              noteCount={noteCountByHighlightId[highlight.id]}
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

      <RelatedContentSection title="Related highlights" rows={highlightRows(relatedContent)} />
    </>
  );
};
