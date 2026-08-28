import { scrollToElementWithHighlight } from '@/components/animations/scrollUtils';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback, useState } from 'react';

/** Book tab routes that share the tag (and optionally search) URL filters. */
type BookTabFilterRoute =
  | '/book/$bookId/highlights'
  | '/book/$bookId/flashcards'
  | '/book/$bookId/notes'
  | '/book/$bookId/structure';

/** The URL filters read/written by these tabs. */
interface BookTabSearch {
  search?: string;
  tagId?: number;
}

/**
 * Shared tag/search URL-filter state for the book feature tabs.
 *
 * Owns the `selectedTagId` mirror of the `tagId` search param (kept in local
 * state so the sidebar highlights immediately) plus the navigate callbacks that
 * were re-implemented near-identically across the highlights, flashcards and
 * notes tabs. `handleChapterClick` applies only to the tabs that scroll to a
 * chapter; every tab may use the search and tag pieces.
 */
export const useBookTabFilters = (from: BookTabFilterRoute) => {
  const search = useSearch({ from }) as BookTabSearch;
  // The navigate signature differs per route; this hook drives all four, so
  // widen the search updater to a plain record. Call sites remain fully
  // typed via the literal `from` argument.
  const navigate = useNavigate({ from }) as unknown as (opts: {
    search: (prev: Record<string, unknown>) => Record<string, unknown>;
    replace?: boolean;
  }) => void;

  const urlSearch = search.search;
  const urlTagId = search.tagId;
  const searchText = urlSearch || '';

  const [selectedTagId, setSelectedTagId] = useState<number | undefined>(urlTagId);

  useResetOnChange([urlTagId], () => setSelectedTagId(urlTagId));

  const handleSearch = useCallback(
    (value: string) => {
      navigate({
        search: (prev) => ({ ...prev, search: value || undefined }),
        replace: true,
      });
    },
    [navigate]
  );

  const handleTagClick = useCallback(
    (newTagId: number | null) => {
      setSelectedTagId(newTagId || undefined);
      navigate({
        search: (prev) => ({ ...prev, tagId: newTagId || undefined }),
        replace: true,
      });
    },
    [navigate]
  );

  /**
   * Unsets every filter the page holds: the search and tag params owned here,
   * plus any extra param names the caller passes (a label, a date range, a
   * kind selection). Pages differ only in that list.
   */
  const clearFilters = useCallback(
    (alsoClear: string[] = []) => {
      setSelectedTagId(undefined);
      navigate({
        search: (prev) => {
          const next: Record<string, unknown> = { ...prev, search: undefined, tagId: undefined };
          for (const key of alsoClear) next[key] = undefined;
          return next;
        },
        replace: true,
      });
    },
    [navigate]
  );

  const handleChapterClick = useCallback(
    (chapterId: number) => {
      if (urlSearch) {
        navigate({
          search: (prev) => ({ ...prev, search: undefined }),
          replace: true,
        });
      }
      scrollToElementWithHighlight(`chapter-${chapterId}`, {
        behavior: 'smooth',
        block: 'start',
      });
    },
    [navigate, urlSearch]
  );

  return {
    searchText,
    selectedTagId,
    setSelectedTagId,
    handleSearch,
    handleTagClick,
    handleChapterClick,
    clearFilters,
  };
};
