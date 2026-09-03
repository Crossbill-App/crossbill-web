import type {
  Bookmark,
  ChapterDigestResponse,
  ChapterWithHighlights,
  Flashcard,
  TagInBook,
} from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { CommonDialogTitle } from '@/components/dialogs/CommonDialogTitle.tsx';
import { DialogTabs, type DialogTabItem } from '@/components/dialogs/DialogTabs.tsx';
import { ProgressBar } from '@/components/dialogs/ProgressBar.tsx';
import { useDialogHorizontalNavigation } from '@/components/dialogs/useDialogHorizontalNavigation.ts';
import type { UrlEntityDialogController } from '@/components/dialogs/useUrlEntityDialog.ts';
import { RelatedContentSection } from '@/components/search/RelatedContentSection.tsx';
import { useRelatedItems } from '@/components/search/useRelatedItems.ts';
import { LinkedNotesSection } from '@/pages/BookPage/Notes/components/LinkedNotesSection.tsx';
import { NoteEditorDialog } from '@/pages/BookPage/Notes/NoteEditorDialog';
import { Box } from '@mui/material';
import { sumBy } from 'lodash';
import { useMemo, useState } from 'react';
import { ChapterGistSection } from './ChapterGistSection.tsx';
import { ChapterReviewSection } from './ChapterReviewSection.tsx';
import { ChapterToolbar } from './ChapterToolbar.tsx';
import { ChatDialog } from './ChatDialog.tsx';
import { CHAT_VARIANT, QUIZ_VARIANT } from './chatVariants.ts';
import { DigestSummarySection } from './DigestSummarySection.tsx';
import { FlashcardsSection } from './FlashcardsSection.tsx';
import { HighlightsSection } from './HighlightsSection.tsx';

interface ChapterDetailDialogProps {
  controller: UrlEntityDialogController<ChapterWithHighlights>;
  bookId: number;
  digestByChapterId: Record<number, ChapterDigestResponse | undefined>;
  bookmarksByHighlightId: Record<number, Bookmark>;
  availableTags: TagInBook[];
  bookFlashcards?: Flashcard[];
}

export const ChapterDetailDialog = ({
  controller,
  bookId,
  digestByChapterId,
  bookmarksByHighlightId,
  availableTags,
  bookFlashcards,
}: ChapterDetailDialogProps) => {
  const [quizOpen, setQuizOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  // Lifted out of DialogTabs so the active tab survives chapter navigation
  // (the tab content remounts inside the chapter-keyed FadeInOut).
  const [activeTab, setActiveTab] = useState(0);
  const [chatNoteBody, setChatNoteBody] = useState<string | null>(null);

  // Callers render this dialog only while a chapter is active
  const chapter = controller.activeItem!;
  const { activeIndex, totalCount, navigateToIndex } = controller;

  const { hasNavigation, navigation } = useDialogHorizontalNavigation({
    currentIndex: activeIndex,
    totalCount,
    onNavigate: navigateToIndex,
  });

  const digestSummary = digestByChapterId[chapter.id];

  const { data: notesData, isLoading: notesLoading } = useGetNotesForBook(bookId, {
    chapter_id: chapter.id,
  });

  // Anchored on the chapter's digest, which is what the whole chapter was
  // embedded as; the strip below sits outside the tabs because one merged
  // ranking belongs to the chapter, not to any one of its tabs.
  const related = useRelatedItems({
    contentId: digestSummary?.id,
    contentType: 'digest',
  });

  // NOTE: the orval axios mutator unwraps the response (`.then(({ data }) => data)`),
  // so the generated GET hook's `data` is the payload itself, not an AxiosResponse.
  const notes = notesData?.items ?? [];

  const highlightCount = chapter.highlights.length;
  const flashcardCount = useMemo(() => {
    const fromHighlights = sumBy(chapter.highlights, (h) => h.flashcards.length);
    const fromChapter = (bookFlashcards ?? []).filter((fc) => fc.chapter_id === chapter.id).length;
    return fromHighlights + fromChapter;
  }, [chapter, bookFlashcards]);

  const title = <CommonDialogTitle>{chapter.name}</CommonDialogTitle>;

  const tabs: DialogTabItem[] = [
    {
      key: 'review',
      label: 'Questions',
      content: (
        <ChapterReviewSection
          chapterId={chapter.id}
          bookId={bookId}
          digestSummary={digestSummary}
          onStartQuiz={() => setQuizOpen(true)}
          onStartChat={() => setChatOpen(true)}
        />
      ),
    },
    {
      key: 'notes',
      label: 'Notes',
      count: notes.length,
      content: (
        <LinkedNotesSection
          bookId={bookId}
          target={{ kind: 'chapter', id: chapter.id }}
          notes={notes}
          isLoading={notesLoading}
        />
      ),
    },
    {
      key: 'highlights',
      label: 'Highlights',
      count: highlightCount,
      content: (
        <HighlightsSection
          chapter={chapter}
          bookId={bookId}
          bookmarksByHighlightId={bookmarksByHighlightId}
          availableTags={availableTags}
        />
      ),
    },
    {
      key: 'flashcards',
      label: 'Flashcards',
      count: flashcardCount,
      content: (
        <FlashcardsSection
          chapter={chapter}
          bookId={bookId}
          digestSummary={digestSummary}
          bookFlashcards={bookFlashcards}
        />
      ),
    },
  ];

  const renderContent = () => (
    <Box>
      <ChapterGistSection chapterId={chapter.id} chapterName={chapter.name} notes={notes} />

      <DigestSummarySection digestSummary={digestSummary} defaultExpanded={true} />

      <ChapterToolbar chapterId={chapter.id} bookId={bookId} hasSummary={!!digestSummary} />

      <DialogTabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      <RelatedContentSection title="Related" rows={related.rows} />
    </Box>
  );

  return (
    <>
      <CommonDialog
        open={controller.activeId !== null}
        onClose={controller.close}
        maxWidth="md"
        title={title}
        headerElement={
          hasNavigation ? (
            <ProgressBar currentIndex={activeIndex} totalCount={totalCount} />
          ) : undefined
        }
        navigation={navigation}
      >
        <FadeInOut ekey={chapter.id}>{renderContent()}</FadeInOut>
      </CommonDialog>
      <ChatDialog
        open={quizOpen}
        onClose={() => setQuizOpen(false)}
        chapterId={chapter.id}
        chapterName={chapter.name}
        variant={QUIZ_VARIANT}
      />
      <ChatDialog
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        chapterId={chapter.id}
        chapterName={chapter.name}
        variant={CHAT_VARIANT}
        onSaveNote={(content) => setChatNoteBody(content)}
      />
      <NoteEditorDialog
        open={chatNoteBody !== null}
        onClose={() => setChatNoteBody(null)}
        initialBody={chatNoteBody ?? ''}
        initialChapterIds={[chapter.id]}
      />
    </>
  );
};
