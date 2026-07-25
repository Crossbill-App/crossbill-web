import type { GetNotesForBookParams } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { useBookTabFilters } from '@/pages/BookPage/common/useBookTabFilters.ts';
import { AddIcon } from '@/theme/Icons.tsx';
import { Alert, Box, Button, Divider } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { useState } from 'react';
import { createPortal } from 'react-dom';

import { MiddleContentColumn } from '@/components/layout/Layouts.tsx';
import { FilterFab } from '../common/FilterFab.tsx';
import { FilterDrawer, type FilterTab } from '../navigation/FilterDrawer.tsx';
import { TagsList } from '../navigation/TagsList/TagsList.tsx';
import { NoteCard } from './NoteCard';
import { NoteModals } from './NoteModals';
import { NoteKindFilter } from './components/NoteKindFilter';
import { useNoteModals } from './hooks/useNoteModals';
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

  const { selectedTagId, handleTagClick } = useBookTabFilters('/book/$bookId/notes');
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
  const noteModals = useNoteModals({ allNotes: visibleNotes });

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
    <MiddleContentColumn>
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

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Button variant="contained" startIcon={<AddIcon />} onClick={noteModals.openCreate}>
          New note
        </Button>
      </Box>

      {isLoading && <Spinner />}
      {isError && <Alert severity="error">Failed to load notes.</Alert>}
      {!isLoading && !isError && visibleNotes.length === 0 && (
        <EmptyStateText>
          {notes.length > 0
            ? 'No notes match the selected filters.'
            : 'No notes yet. Create notes about characters, terms, and concepts as you read.'}
        </EmptyStateText>
      )}

      <CardList>
        {visibleNotes.map((note) => (
          <li key={note.id}>
            <NoteCard note={note} onClick={() => noteModals.openView(note)} />
          </li>
        ))}
      </CardList>

      {!isDesktop &&
        fabContainerEl &&
        createPortal(
          <FilterFab
            filterEnabled={!!selectedTagId || kindFilterActive}
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

      <NoteModals controller={noteModals} />
    </MiddleContentColumn>
  );
};
