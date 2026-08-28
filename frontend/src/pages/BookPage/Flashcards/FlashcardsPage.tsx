import type {
  ChapterWithHighlights,
  Flashcard,
  Highlight,
  TagGroupInBook,
  TagInBook,
} from '@/api/generated/model';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import {
  FlashcardChapterList,
  type FlashcardChapterData,
  type FlashcardWithContext,
} from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { ContentWithSidebar } from '@/components/layout/Layouts.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { FilteredEmptyState } from '@/pages/BookPage/common/FilteredEmptyState.tsx';
import { ListSearchSortHeader } from '@/pages/BookPage/common/ListSearchSortHeader.tsx';
import { useBookTabFilters } from '@/pages/BookPage/common/useBookTabFilters.ts';
import { BOOK_PAGE_LABELS } from '@/pages/BookPage/navigation/bookPageRoutes.ts';
import { ChapterNav, type ChapterNavigationData } from '@/pages/BookPage/navigation/ChapterNav.tsx';
import { Box, Divider } from '@mui/material';
import { flatMap } from 'lodash';
import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { FilterFab } from '../common/FilterFab.tsx';
import { FilterDrawer, type FilterTab } from '../navigation/FilterDrawer.tsx';
import { TagsList } from '../navigation/TagsList/TagsList.tsx';
import { FlashcardEditDialog } from './FlashcardEditDialog.tsx';

const BOOK_FLASHCARDS_KEY = -1;

/**
 * Heading for the group of cards tied to no chapter. Named for what the group
 * is rather than for the API's `book_flashcards`, which read as a chapter with
 * an odd name under the same heading style as the real ones.
 */
const NOT_IN_A_CHAPTER = 'Not in a chapter';

export const FlashcardsPage = () => {
  const { book, isDesktop, leftSidebarEl, fabContainerEl } = useBookPage();

  const {
    searchText,
    selectedTagId,
    handleSearch,
    handleTagClick,
    handleChapterClick,
    clearFilters,
  } = useBookTabFilters('/book/$bookId/flashcards');
  const [isReversed, setIsReversed] = useState(false);
  const [editingFlashcard, setEditingFlashcard] = useState<FlashcardWithContext | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const bookChapters = book.chapters;

  // Build a map of chapter IDs to chapter names for resolving chapter-linked flashcards
  const chapterNameMap = useMemo(() => {
    const map: Record<number, string> = {};
    for (const ch of bookChapters) {
      map[ch.id] = ch.name || 'Unknown chapter';
    }
    return map;
  }, [bookChapters]);

  // Extract all flashcards with context from book chapters
  const allFlashcardsWithContext = useMemo((): FlashcardWithContext[] => {
    const highlightFlashcards = flatMap(bookChapters, (chapter: ChapterWithHighlights) =>
      flatMap(chapter.highlights, (highlight: Highlight) =>
        highlight.flashcards.map((flashcard: Flashcard) => ({
          ...flashcard,
          highlight: highlight,
          chapterName: chapter.name || 'Unknown chapter',
          chapterId: chapter.id,
          tags: highlight.tags,
        }))
      )
    );

    // book_flashcards includes both truly book-level (no chapter_id) and
    // chapter-linked (chapter_id set, highlight_id null) flashcards
    const bookLevelFlashcards: FlashcardWithContext[] = (book.book_flashcards ?? []).map((fc) => ({
      ...fc,
      highlight: null,
      chapterName: fc.chapter_id
        ? (chapterNameMap[fc.chapter_id] ?? 'Unknown chapter')
        : NOT_IN_A_CHAPTER,
      chapterId: fc.chapter_id ?? null,
      tags: [],
    }));

    return [...highlightFlashcards, ...bookLevelFlashcards];
  }, [bookChapters, book.book_flashcards, chapterNameMap]);

  // Filter flashcards by tag and search
  const filteredFlashcards = useMemo((): FlashcardWithContext[] => {
    let result = allFlashcardsWithContext;

    // Filter by tag
    if (selectedTagId) {
      result = result.filter((fc) => fc.tags.some((tag) => tag.id === selectedTagId));
    }

    // Filter by search (question or answer)
    if (searchText) {
      const lowerSearch = searchText.toLowerCase();
      result = result.filter(
        (fc) =>
          fc.question.toLowerCase().includes(lowerSearch) ||
          fc.answer.toLowerCase().includes(lowerSearch)
      );
    }

    return result;
  }, [allFlashcardsWithContext, selectedTagId, searchText]);

  // Group flashcards by chapter
  const flashcardChapters = useMemo((): FlashcardChapterData[] => {
    const grouped: Partial<Record<number, FlashcardWithContext[]>> = {};
    for (const fc of filteredFlashcards) {
      const key = fc.chapterId ?? BOOK_FLASHCARDS_KEY;
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key]!.push(fc);
    }

    // Separate book-level flashcards from chapter flashcards
    const bookFlashcardsGroup = grouped[BOOK_FLASHCARDS_KEY];
    delete grouped[BOOK_FLASHCARDS_KEY];

    const chapterResults: FlashcardChapterData[] = Object.entries(grouped)
      .filter((entry): entry is [string, FlashcardWithContext[]] => entry[1] !== undefined)
      .map(([chapterId, flashcards]) => ({
        id: Number(chapterId),
        name: flashcards[0].chapterName,
        flashcards,
      }));

    // Append book-level flashcards at the end
    if (bookFlashcardsGroup && bookFlashcardsGroup.length > 0) {
      chapterResults.push({
        id: BOOK_FLASHCARDS_KEY,
        name: NOT_IN_A_CHAPTER,
        listLabel: 'Flashcards not in a chapter',
        flashcards: bookFlashcardsGroup,
      });
    }

    if (isReversed) {
      return [...chapterResults].reverse().map((chapter) => ({
        ...chapter,
        flashcards: [...chapter.flashcards].reverse(),
      }));
    }

    return chapterResults;
  }, [filteredFlashcards, isReversed]);

  const emptyState =
    searchText || selectedTagId ? (
      <FilteredEmptyState noun="flashcards" onClearFilters={() => clearFilters()} />
    ) : (
      <EmptyStateText>
        No flashcards yet. Create flashcards from your highlights to start studying.
      </EmptyStateText>
    );

  const navData = useFlashcardsPageData(
    allFlashcardsWithContext,
    flashcardChapters,
    bookChapters,
    book.tags
  );

  const filterTabs = useFlashcardsFilterTabs({
    navChapters: navData.chapters,
    tags: navData.tags,
    tagGroups: book.tag_groups,
    bookId: book.id,
    selectedTagId,
    handleChapterClick,
    handleTagClick,
    setFilterDrawerOpen,
  });

  return (
    <>
      {/* Desktop: portal Tags into left sidebar */}
      {isDesktop &&
        leftSidebarEl &&
        createPortal(
          <FlashcardsSidebar
            tags={navData.tags}
            tagGroups={book.tag_groups}
            bookId={book.id}
            selectedTagId={selectedTagId}
            onTagClick={handleTagClick}
          />,
          leftSidebarEl
        )}

      {/* Content */}
      {isDesktop ? (
        <ContentWithSidebar>
          <Box>
            <PageTitle text={BOOK_PAGE_LABELS.flashcards} />
            <ListSearchSortHeader
              onSearch={handleSearch}
              searchPlaceholder="Search flashcards..."
              searchInitialValue={searchText}
              isReversed={isReversed}
              onToggleReversed={() => setIsReversed(!isReversed)}
            />
            <FlashcardChapterList
              chapters={flashcardChapters}
              bookId={book.id}
              emptyState={emptyState}
              animationKey="flashcards"
              onEditFlashcard={setEditingFlashcard}
            />
          </Box>
          <ChapterNav chapters={navData.chapters} onChapterClick={handleChapterClick} />
        </ContentWithSidebar>
      ) : (
        <>
          <PageTitle text={BOOK_PAGE_LABELS.flashcards} />
          <ListSearchSortHeader
            onSearch={handleSearch}
            searchPlaceholder="Search flashcards..."
            searchInitialValue={searchText}
            isReversed={isReversed}
            onToggleReversed={() => setIsReversed(!isReversed)}
          />
          <FlashcardChapterList
            chapters={flashcardChapters}
            bookId={book.id}
            emptyState={emptyState}
            animationKey="flashcards"
            onEditFlashcard={setEditingFlashcard}
          />
          {fabContainerEl &&
            createPortal(
              <FilterFab
                activeFilterCount={selectedTagId ? 1 : 0}
                onClick={() => setFilterDrawerOpen(true)}
              />,
              fabContainerEl
            )}
          <FilterDrawer
            open={filterDrawerOpen}
            onClose={() => setFilterDrawerOpen(false)}
            tabs={filterTabs}
          />
        </>
      )}

      {editingFlashcard && (
        <FlashcardEditDialog
          flashcard={editingFlashcard}
          bookId={book.id}
          open={!!editingFlashcard}
          onClose={() => setEditingFlashcard(null)}
        />
      )}
    </>
  );
};

// --- Extracted subcomponents ---

interface FlashcardsSidebarProps {
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  bookId: number;
  selectedTagId: number | undefined;
  onTagClick: (tagId: number | null) => void;
}

const FlashcardsSidebar = ({
  tags,
  tagGroups,
  bookId,
  selectedTagId,
  onTagClick,
}: FlashcardsSidebarProps) => (
  <>
    <Divider sx={{ mb: 4 }} />
    <TagsList
      tags={tags}
      tagGroups={tagGroups}
      bookId={bookId}
      selectedTag={selectedTagId}
      onTagClick={onTagClick}
      hideEmptyGroups
    />
  </>
);

interface UseFlashcardsFilterTabsParams {
  navChapters: ChapterNavigationData[];
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  bookId: number;
  selectedTagId: number | undefined;
  handleChapterClick: (chapterId: number) => void;
  handleTagClick: (tagId: number | null) => void;
  setFilterDrawerOpen: (open: boolean) => void;
}

const useFlashcardsFilterTabs = ({
  navChapters,
  tags,
  tagGroups,
  bookId,
  selectedTagId,
  handleChapterClick,
  handleTagClick,
  setFilterDrawerOpen,
}: UseFlashcardsFilterTabsParams): FilterTab[] =>
  useMemo(
    () => [
      {
        label: 'Chapters',
        content: (
          <ChapterNav
            chapters={navChapters}
            onChapterClick={(id) => {
              handleChapterClick(id);
              setFilterDrawerOpen(false);
            }}
            hideTitle
          />
        ),
      },
      {
        label: 'Tags',
        content: (
          <TagsList
            tags={tags}
            tagGroups={tagGroups}
            bookId={bookId}
            selectedTag={selectedTagId}
            onTagClick={(id) => {
              handleTagClick(id);
              setFilterDrawerOpen(false);
            }}
            hideTitle
            hideEmptyGroups
          />
        ),
      },
    ],
    [
      navChapters,
      tags,
      handleChapterClick,
      tagGroups,
      bookId,
      selectedTagId,
      handleTagClick,
      setFilterDrawerOpen,
    ]
  );

// --- Private hooks ---

const useFlashcardsPageData = (
  allFlashcardsWithContext: FlashcardWithContext[],
  chapters: FlashcardChapterData[],
  bookChapters: ChapterWithHighlights[],
  tagsInBook: TagInBook[] | undefined
) => {
  const tagsWithFlashcards = useMemo(() => {
    if (!tagsInBook) return [];

    const tagIdsWithFlashcards = new Set<number>();
    allFlashcardsWithContext.forEach((fc) =>
      fc.tags.forEach((tag) => tagIdsWithFlashcards.add(tag.id))
    );

    return tagsInBook.filter((tag) => tagIdsWithFlashcards.has(tag.id));
  }, [tagsInBook, allFlashcardsWithContext]);

  // The sidebar carries both counts on both tabs, so a chapter reads the same
  // wherever it is listed. Highlights are not on `FlashcardChapterData`, so
  // they come from the book; the "Not in a chapter" bucket matches none and
  // gets no highlight count.
  const navChapters: ChapterNavigationData[] = useMemo(() => {
    const highlightCountById = new Map(bookChapters.map((ch) => [ch.id, ch.highlights.length]));
    return chapters.map((ch) => ({
      id: ch.id,
      name: ch.name,
      highlightCount: highlightCountById.get(ch.id) ?? 0,
      flashcardCount: ch.flashcards.length,
    }));
  }, [chapters, bookChapters]);

  return {
    chapters: navChapters,
    tags: tagsWithFlashcards,
  };
};
