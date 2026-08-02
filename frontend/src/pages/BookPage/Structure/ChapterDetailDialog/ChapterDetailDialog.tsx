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
import { CommonDialogHorizontalNavigation } from '@/components/dialogs/CommonDialogHorizontalNavigation.tsx';
import { CommonDialogTitle } from '@/components/dialogs/CommonDialogTitle.tsx';
import { DialogTabs, type DialogTabItem } from '@/components/dialogs/DialogTabs.tsx';
import { ProgressBar } from '@/components/dialogs/ProgressBar.tsx';
import {
  useDialogHorizontalNavigation,
  useDialogSwipeNavigation,
} from '@/components/dialogs/useDialogHorizontalNavigation.ts';
import type { UrlEntityDialogController } from '@/components/dialogs/useUrlEntityDialog.ts';
import { LinkedNotesSection } from '@/pages/BookPage/Notes/components/LinkedNotesSection.tsx';
import { NoteEditorDialog } from '@/pages/BookPage/Notes/NoteEditorDialog';
import { Box, Button } from '@mui/material';
import { sumBy } from 'lodash';
import { useMemo, useState } from 'react';
import { ChapterGistSection } from './ChapterGistSection.tsx';
import { ChapterReviewSection } from './ChapterReviewSection.tsx';
import { ChapterToolbar } from './ChapterToolbar.tsx';
import { ChatDialog } from './ChatDialog.tsx';
import { CHAT_VARIANT, QUIZ_VARIANT } from './chatVariants.ts';
import { FlashcardsSection } from './FlashcardsSection.tsx';
import { HighlightsSection } from './HighlightsSection.tsx';
import { DigestSummarySection } from './DigestSummarySection.tsx';

interface ChapterDetailDialogProps {
  controller: UrlEntityDialogController<ChapterWithHighlights>;
  bookId: number;
  digestByChapterId: Record<number, ChapterDigestResponse>;
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

  const { hasNavigation, hasPrevious, hasNext, handlePrevious, handleNext } =
    useDialogHorizontalNavigation({
      open: controller.activeId !== null,
      currentIndex: activeIndex,
      totalCount,
      onNavigate: navigateToIndex,
    });

  const { swipeHandlers: summarySwipeHandlers } = useDialogSwipeNavigation({
    currentIndex: activeIndex,
    totalCount,
    onNavigate: navigateToIndex,
  });

  const { swipeHandlers: tabSwipeHandlers } = useDialogSwipeNavigation({
    currentIndex: activeIndex,
    totalCount,
    onNavigate: navigateToIndex,
  });

  const digestSummary = digestByChapterId[chapter.id];

  const { data: notesData, isLoading: notesLoading } = useGetNotesForBook(bookId, {
    chapter_id: chapter.id,
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
      label: 'Chapter review',
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

      <Box {...summarySwipeHandlers}>
        <DigestSummarySection digestSummary={digestSummary} defaultExpanded={true} />
      </Box>

      <ChapterToolbar chapterId={chapter.id} bookId={bookId} hasSummary={!!digestSummary} />

      <DialogTabs
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        panelSwipeHandlers={tabSwipeHandlers}
      />
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
        footerActions={
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
            <Button onClick={controller.close}>Close</Button>
          </Box>
        }
      >
        <CommonDialogHorizontalNavigation
          hasNavigation={hasNavigation}
          hasPrevious={hasPrevious}
          hasNext={hasNext}
          onPrevious={handlePrevious}
          onNext={handleNext}
        >
          <FadeInOut ekey={chapter.id}>{renderContent()}</FadeInOut>
        </CommonDialogHorizontalNavigation>
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
