import type { GetNotesForBookParams } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { SemanticSearchField } from '@/components/search/SemanticSearchField.tsx';
import { useSemanticSearch } from '@/components/search/useSemanticSearch.ts';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { FilteredEmptyState } from '@/pages/BookPage/common/FilteredEmptyState.tsx';
import { PageHeader } from '@/pages/BookPage/common/PageHeader.tsx';
import { useBookTabFilters } from '@/pages/BookPage/common/useBookTabFilters.ts';
import { AddIcon } from '@/theme/Icons.tsx';
import { Alert, Divider, IconButton } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { useState } from 'react';
import { createPortal } from 'react-dom';

import { BOOK_PAGE_LABELS } from '@/pages/BookPage/navigation/bookPageRoutes.ts';
import { FilterFab } from '../common/FilterFab.tsx';
import { FilterDrawer, type FilterTab } from '../navigation/FilterDrawer.tsx';
import { TagsList } from '../navigation/TagsList/TagsList.tsx';
import { NoteCard } from './NoteCard';
import { NoteDialogs } from './NoteDialogs';
import { NoteKindFilter } from './components/NoteKindFilter';
import { useNoteDialogs } from './hooks/useNoteDialogs';
import {
  DEFAULT_NOTE_KINDS,
  type NoteKindValue,
  isDefaultKindSelection,
  noteKindOf,
} from './noteKinds';

export const NotesPage = () => {
  const { book, isDesktop, leftSidebarEl, fabContainerEl } = useBookPage();
  const navigate = useNavigate({ from: '/book/$bookId/notes' });
  const { kinds, chapterId } = useSearch({ from: '/book/$bookId/notes' });

  const { searchText, handleSearch, selectedTagId, handleTagClick, clearFilters } =
    useBookTabFilters('/book/$bookId/notes');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const selectedKinds = kinds ?? DEFAULT_NOTE_KINDS;
  const kindFilterActive = kinds !== undefined;

  const params: GetNotesForBookParams = {
    chapter_id: chapterId,
    tag_id: selectedTagId,
  };
  const { data, isLoading, isError } = useGetNotesForBook(book.id, params);
  // NOTE: the orval axios mutator unwraps the response (`.then(({ data }) => data)`),
  // so the generated GET hook's `data` is the payload itself, not an AxiosResponse.
  const notes = data?.items ?? [];
  const visibleNotes = notes.filter((note) => selectedKinds.includes(noteKindOf(note.kind)));

  const search = useSemanticSearch({ query: searchText, bookId: book.id });
  const scoreByNoteId = new Map(search.results?.notes.map((hit) => [hit.id, hit.score]) ?? []);

  // The search intersects with the kind and tag filters rather than replacing
  // them: a note must pass all of them. Matches are ordered best first.
  const notesToShow = search.results
    ? visibleNotes
        .filter((note) => scoreByNoteId.has(note.id))
        .sort((a, b) => (scoreByNoteId.get(b.id) ?? 0) - (scoreByNoteId.get(a.id) ?? 0))
    : visibleNotes;

  const filtersActive =
    search.hasQuery || kindFilterActive || !!selectedTagId || chapterId !== undefined;

  const noteDialogs = useNoteDialogs({ allNotes: notesToShow });

  const handleKindsChange = (next: NoteKindValue[]) => {
    void navigate({
      search: (prev) => ({
        ...prev,
        kinds: isDefaultKindSelection(next) ? undefined : next,
      }),
      replace: true,
    });
  };

  const filterTabs: FilterTab[] = [
    {
      label: 'Types',
      content: <NoteKindFilter selected={selectedKinds} onChange={handleKindsChange} hideTitle />,
    },
    {
      label: 'Tags',
      content: (
        <TagsList
          tags={book.tags}
          tagGroups={book.tag_groups}
          bookId={book.id}
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
  ];

  return (
    <>
      {isDesktop &&
        leftSidebarEl &&
        createPortal(
          <>
            <Divider sx={{ mb: 4 }} />
            <NoteKindFilter selected={selectedKinds} onChange={handleKindsChange} />
            <Divider sx={{ my: 4 }} />
            <TagsList
              tags={book.tags}
              tagGroups={book.tag_groups}
              bookId={book.id}
              selectedTag={selectedTagId}
              onTagClick={handleTagClick}
              hideEmptyGroups
            />
          </>,
          leftSidebarEl
        )}

      <PageHeader
        title={BOOK_PAGE_LABELS.notes}
        search={
          <SemanticSearchField
            value={searchText}
            onChange={handleSearch}
            placeholder="Search notes by meaning..."
          />
        }
        action={
          <IconButton aria-label="Add note" color="primary" onClick={noteDialogs.openCreate}>
            <AddIcon />
          </IconButton>
        }
      />

      {search.isError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Search failed. Showing all notes.
        </Alert>
      )}

      {isLoading && <Spinner />}
      {isError && <Alert severity="error">Failed to load notes.</Alert>}
      {!isLoading &&
        !isError &&
        notesToShow.length === 0 &&
        (filtersActive ? (
          <FilteredEmptyState
            noun="notes"
            onClearFilters={() => clearFilters(['kinds', 'chapterId'])}
          />
        ) : (
          <EmptyStateText>
            No notes yet. Create notes about characters, terms, and concepts as you read.
          </EmptyStateText>
        ))}

      <CardList>
        {notesToShow.map((note) => (
          <li key={note.id}>
            <NoteCard note={note} onClick={() => noteDialogs.openView(note)} />
          </li>
        ))}
      </CardList>

      {!isDesktop &&
        fabContainerEl &&
        createPortal(
          <FilterFab
            activeFilterCount={[!!selectedTagId, kindFilterActive].filter(Boolean).length}
            onClick={() => setFilterDrawerOpen(true)}
          />,
          fabContainerEl
        )}
      {!isDesktop && (
        <FilterDrawer
          open={filterDrawerOpen}
          onClose={() => setFilterDrawerOpen(false)}
          tabs={filterTabs}
        />
      )}

      <NoteDialogs controller={noteDialogs} />
    </>
  );
};
