import { NotesPage } from '@/pages/BookPage/Notes/NotesPage';
import { type NoteKindValue, isNoteKind } from '@/pages/BookPage/Notes/noteKinds';
import { createFileRoute } from '@tanstack/react-router';

type NotesSearch = {
  kinds?: NoteKindValue[];
  chapterId?: number;
  tagId?: number;
  noteId?: number;
  search?: string;
};

export const Route = createFileRoute('/book/$bookId/notes')({
  component: NotesPage,
  validateSearch: (search: Record<string, unknown>): NotesSearch => ({
    kinds: Array.isArray(search.kinds) ? search.kinds.filter(isNoteKind) : undefined,
    chapterId: (search.chapterId as number | undefined) || undefined,
    tagId: (search.tagId as number | undefined) || undefined,
    noteId: (search.noteId as number | undefined) || undefined,
    search: (search.search as string | undefined) || undefined,
  }),
});
