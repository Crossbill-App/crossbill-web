import { useSearchBookHighlights } from '@/api/generated/highlights/highlights.ts';
import type {
  Bookmark,
  ChapterWithHighlights,
  Highlight,
  TagGroupInBook,
  TagInBook,
} from '@/api/generated/model';
import { useGetTags } from '@/api/generated/tags/tags.ts';
import { scrollToElementWithHighlight } from '@/components/animations/scrollUtils';
import { ContentWithSidebar } from '@/components/layout/Layouts.tsx';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { ListSearchSortHeader } from '@/pages/BookPage/common/ListSearchSortHeader.tsx';
import { useBookTabFilters } from '@/pages/BookPage/common/useBookTabFilters.ts';
import { useHighlightDialog } from '@/pages/BookPage/Highlights/hooks/useHighlightDialog.ts';
import { Box, Divider } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { keyBy } from 'lodash';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { FilterFab } from '../common/FilterFab.tsx';
import { BookmarkList } from '../navigation/BookmarkList.tsx';
import { ChapterNav, type ChapterNavigationData } from '../navigation/ChapterNav.tsx';
import { FilterDrawer, type FilterTab } from '../navigation/FilterDrawer.tsx';
import { HighlightLabelsList } from '../navigation/HighlightLabelsList.tsx';
import { TagsList } from '../navigation/TagsList/TagsList.tsx';
import { HighlightsList, type ChapterData } from './HighlightsList.tsx';
import { HighlightViewDialog } from './HighlightViewDialog';

export const HighlightsPage = () => {
  const { book, isDesktop, leftSidebarEl, fabContainerEl } = useBookPage();

  const { search: urlSearch, labelId: urlLabelId } = useSearch({
    from: '/book/$bookId/highlights',
  });
  const navigate = useNavigate({ from: '/book/$bookId/highlights' });

  const { searchText, selectedTagId, handleSearch, handleTagClick, handleChapterClick } =
    useBookTabFilters('/book/$bookId/highlights');
  const [selectedLabelId, setSelectedLabelId] = useState<number | undefined>(urlLabelId);
  const [isReversed, setIsReversed] = useState(false);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const filterEnabled = !!selectedLabelId || !!selectedTagId;

  useEffect(() => {
    setSelectedLabelId(urlLabelId);
  }, [urlLabelId]);

  // Fetch available tags for the highlight dialog
  const { data: tagsResponse } = useGetTags(book.id);

  const handleLabelClick = useCallback(
    (newLabelId: number | null) => {
      setSelectedLabelId(newLabelId || undefined);
      navigate({
        search: (prev) => ({ ...prev, labelId: newLabelId || undefined }),
        replace: true,
      });
    },
    [navigate]
  );

  const handleBookmarkClick = useCallback(
    (highlightId: number) => {
      if (urlSearch) {
        navigate({
          search: (prev) => ({ ...prev, search: undefined }),
          replace: true,
        });
      }
      scrollToElementWithHighlight(`highlight-${highlightId}`, { behavior: 'smooth' });
    },
    [navigate, urlSearch]
  );

  const bookSearch = useBookSearch(book.id, searchText);

  const bookmarksByHighlightId = useMemo(
    () => keyBy(book.bookmarks, 'highlight_id'),
    [book.bookmarks]
  );

  const chapters: ChapterData[] = useMemo(() => {
    const toFilter = bookSearch.showSearchResults
      ? bookSearch.chapters
      : book.chapters.filter((chapter) => chapter.highlights.length > 0);

    const result = filterChaptersByLabel(
      selectedLabelId,
      filterChaptersByTag(selectedTagId, toFilter)
    ).map((chapter) => ({
      id: chapter.id,
      name: chapter.name || 'Unknown Chapter',
      chapterNumber: chapter.chapter_number ?? undefined,
      highlights: chapter.highlights,
    }));

    if (isReversed) {
      return [...result].reverse().map((chapter) => ({
        ...chapter,
        highlights: [...chapter.highlights].reverse(),
      }));
    }

    return result;
  }, [
    bookSearch.showSearchResults,
    bookSearch.chapters,
    isReversed,
    book.chapters,
    selectedTagId,
    selectedLabelId,
  ]);

  const allHighlights = useMemo(() => {
    return chapters.flatMap((chapter) => chapter.highlights);
  }, [chapters]);

  const highlightDialog = useHighlightDialog({ allHighlights, isMobile: !isDesktop });

  const tags = book.tags;

  const navData = useHighlightsPageData(chapters);

  const emptyMessage = useMemo(() => {
    if (bookSearch.showSearchResults) {
      if (selectedTagId && selectedLabelId)
        return 'No highlights found matching your search with the selected tag and label.';
      if (selectedTagId) return 'No highlights found matching your search with the selected tag.';
      if (selectedLabelId)
        return 'No highlights found matching your search with the selected label.';
      return 'No highlights found matching your search.';
    }
    if (selectedTagId && selectedLabelId)
      return 'No highlights found with the selected tag and label.';
    if (selectedTagId) return 'No highlights found with the selected tag.';
    if (selectedLabelId) return 'No highlights found with the selected label.';
    return 'No chapters found for this book.';
  }, [bookSearch.showSearchResults, selectedTagId, selectedLabelId]);

  const filterTabs = useHighlightsFilterTabs({
    navChapters: navData.chapters,
    tags,
    tagGroups: book.tag_groups,
    bookId: book.id,
    bookmarks: book.bookmarks,
    allHighlights,
    selectedTagId,
    selectedLabelId,
    handleChapterClick,
    handleTagClick,
    handleLabelClick,
    handleBookmarkClick,
    setFilterDrawerOpen,
  });

  return (
    <>
      {/* Desktop: portal left sidebar content */}
      {isDesktop &&
        leftSidebarEl &&
        createPortal(
          <HighlightsSidebar
            tags={tags}
            tagGroups={book.tag_groups}
            bookId={book.id}
            selectedTagId={selectedTagId}
            onTagClick={handleTagClick}
            selectedLabelId={selectedLabelId}
            onLabelClick={handleLabelClick}
          />,
          leftSidebarEl
        )}

      {/* Content */}
      {isDesktop ? (
        <ContentWithSidebar>
          <Box>
            <ListSearchSortHeader
              onSearch={handleSearch}
              searchPlaceholder="Search highlights..."
              searchInitialValue={searchText}
              isReversed={isReversed}
              onToggleReversed={() => setIsReversed(!isReversed)}
            />
            <HighlightsList
              chapters={chapters}
              bookmarksByHighlightId={bookmarksByHighlightId}
              isLoading={bookSearch.isSearching}
              emptyMessage={emptyMessage}
              animationKey="chapters-highlights"
              onOpenHighlight={highlightDialog.open}
            />
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <BookmarkList
              bookmarks={book.bookmarks}
              allHighlights={allHighlights}
              onBookmarkClick={handleBookmarkClick}
            />
            <Divider />
            <ChapterNav
              chapters={navData.chapters}
              onChapterClick={handleChapterClick}
              countType="highlight"
            />
          </Box>
        </ContentWithSidebar>
      ) : (
        <>
          <ListSearchSortHeader
            onSearch={handleSearch}
            searchPlaceholder="Search highlights..."
            searchInitialValue={searchText}
            isReversed={isReversed}
            onToggleReversed={() => setIsReversed(!isReversed)}
          />
          <HighlightsList
            chapters={chapters}
            bookmarksByHighlightId={bookmarksByHighlightId}
            isLoading={bookSearch.isSearching}
            emptyMessage={emptyMessage}
            animationKey="chapters-highlights"
            onOpenHighlight={highlightDialog.open}
          />

          {fabContainerEl &&
            createPortal(
              <FilterFab filterEnabled={filterEnabled} onClick={() => setFilterDrawerOpen(true)} />,
              fabContainerEl
            )}

          <FilterDrawer
            open={filterDrawerOpen}
            onClose={() => setFilterDrawerOpen(false)}
            tabs={filterTabs}
          />
        </>
      )}

      {/* Highlight dialog */}
      {highlightDialog.activeItem && (
        <HighlightViewDialog
          controller={highlightDialog}
          bookId={book.id}
          availableTags={tagsResponse?.items || []}
          bookmarksByHighlightId={bookmarksByHighlightId}
        />
      )}
    </>
  );
};

// --- Extracted subcomponents ---

interface HighlightsSidebarProps {
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  bookId: number;
  selectedTagId: number | undefined;
  onTagClick: (tagId: number | null) => void;
  selectedLabelId: number | undefined;
  onLabelClick: (labelId: number | null) => void;
}

const HighlightsSidebar = ({
  tags,
  tagGroups,
  bookId,
  selectedTagId,
  onTagClick,
  selectedLabelId,
  onLabelClick,
}: HighlightsSidebarProps) => (
  <>
    <Divider sx={{ mb: 4 }} />
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <TagsList
        tags={tags}
        tagGroups={tagGroups}
        bookId={bookId}
        selectedTag={selectedTagId}
        onTagClick={onTagClick}
      />
      <HighlightLabelsList
        bookId={bookId}
        selectedLabelId={selectedLabelId}
        onLabelClick={onLabelClick}
      />
    </Box>
  </>
);

interface UseHighlightsFilterTabsParams {
  navChapters: ChapterNavigationData[];
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  bookId: number;
  bookmarks: Bookmark[];
  allHighlights: Highlight[];
  selectedTagId: number | undefined;
  selectedLabelId: number | undefined;
  handleChapterClick: (chapterId: number) => void;
  handleTagClick: (tagId: number | null) => void;
  handleLabelClick: (labelId: number | null) => void;
  handleBookmarkClick: (highlightId: number) => void;
  setFilterDrawerOpen: (open: boolean) => void;
}

const useHighlightsFilterTabs = ({
  navChapters,
  tags,
  tagGroups,
  bookId,
  bookmarks,
  allHighlights,
  selectedTagId,
  selectedLabelId,
  handleChapterClick,
  handleTagClick,
  handleLabelClick,
  handleBookmarkClick,
  setFilterDrawerOpen,
}: UseHighlightsFilterTabsParams): FilterTab[] =>
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
            countType="highlight"
          />
        ),
      },
      {
        label: 'Tags',
        content: (
          <Box>
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
            />
            <Box sx={{ mt: 3 }}>
              <HighlightLabelsList
                bookId={bookId}
                selectedLabelId={selectedLabelId}
                onLabelClick={(id) => {
                  handleLabelClick(id);
                  setFilterDrawerOpen(false);
                }}
              />
            </Box>
          </Box>
        ),
      },
      {
        label: 'Bookmarks',
        content: (
          <BookmarkList
            bookmarks={bookmarks}
            allHighlights={allHighlights}
            onBookmarkClick={(id) => {
              handleBookmarkClick(id);
              setFilterDrawerOpen(false);
            }}
            hideTitle
          />
        ),
      },
    ],
    [
      navChapters,
      handleChapterClick,
      tags,
      tagGroups,
      bookId,
      bookmarks,
      selectedTagId,
      handleTagClick,
      selectedLabelId,
      handleLabelClick,
      allHighlights,
      handleBookmarkClick,
      setFilterDrawerOpen,
    ]
  );

// --- Private hooks and helpers ---

const useHighlightsPageData = (chapters: ChapterData[]) => {
  const navChapters: ChapterNavigationData[] = useMemo(() => {
    return chapters.map((chapter) => ({
      id: chapter.id,
      name: chapter.name,
      itemCount: chapter.highlights.length,
    }));
  }, [chapters]);

  return {
    chapters: navChapters,
  };
};

const useBookSearch = (bookId: number, searchText: string) => {
  const { data: searchResults, isLoading: isSearching } = useSearchBookHighlights(
    bookId,
    {
      searchText: searchText || 'placeholder',
    },
    {
      query: {
        enabled: searchText.length > 0,
      },
    }
  );

  const showSearchResults = searchText.length > 0;

  return {
    showSearchResults,
    chapters: searchResults?.chapters || [],
    isSearching: isSearching && showSearchResults,
  };
};

function filterChaptersByTag(
  selectedTagId: number | undefined,
  chaptersWithHighlights: ChapterWithHighlights[]
) {
  if (!selectedTagId) {
    return chaptersWithHighlights;
  }

  return chaptersWithHighlights
    .map((chapter) => ({
      ...chapter,
      highlights: chapter.highlights.filter((highlight) =>
        highlight.tags.some((tag) => tag.id === selectedTagId)
      ),
    }))
    .filter((chapter) => chapter.highlights.length > 0);
}

function filterChaptersByLabel(
  selectedLabelId: number | undefined,
  chaptersWithHighlights: ChapterWithHighlights[]
) {
  if (!selectedLabelId) {
    return chaptersWithHighlights;
  }

  return chaptersWithHighlights
    .map((chapter) => ({
      ...chapter,
      highlights: chapter.highlights.filter(
        (highlight) => highlight.label?.highlight_style_id === selectedLabelId
      ),
    }))
    .filter((chapter) => chapter.highlights.length > 0);
}
