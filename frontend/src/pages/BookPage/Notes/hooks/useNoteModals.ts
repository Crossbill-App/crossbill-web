import type { NoteWithLinks } from '@/api/generated/model';
import { getGetNoteQueryKey } from '@/api/generated/notes/notes.ts';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback, useRef, useState } from 'react';

interface UseNoteModalsOptions {
  syncToUrl?: boolean;
  /** Ordered notes for prev/next navigation in the view modal (e.g. the filtered list). */
  allNotes?: NoteWithLinks[];
}

export interface NoteModalsController {
  openCreate: () => void;
  openView: (note: NoteWithLinks) => void;
  editorOpen: boolean;
  closeEditor: () => void;
  viewingNoteId: number | null;
  closeView: () => void;
  /** Index of the viewed note in `allNotes`; -1 when unknown (no navigation). */
  currentNoteIndex: number;
  totalCount: number;
  handleModalNavigate: (newIndex: number) => void;
}

export const useNoteModals = (options: UseNoteModalsOptions = {}): NoteModalsController => {
  const { syncToUrl = true, allNotes = [] } = options;
  const queryClient = useQueryClient();

  const [editorOpen, setEditorOpen] = useState(false);

  const search = useSearch({ strict: false }) as { noteId?: number };
  const navigate = useNavigate() as (opts: {
    search: (prev: Record<string, unknown>) => Record<string, unknown>;
    replace?: boolean;
  }) => Promise<void>;

  const [localNoteId, setLocalNoteId] = useState<number | null>(null);
  const wasOpenedByPush = useRef(false);

  const viewingNoteId = syncToUrl ? (search.noteId ?? null) : localNoteId;

  const setNoteId = useCallback(
    (noteId: number | undefined, replace: boolean) => {
      if (syncToUrl) {
        void navigate({
          search: (prev) => ({ ...prev, noteId }),
          replace,
        });
      } else {
        setLocalNoteId(noteId ?? null);
      }
    },
    [navigate, syncToUrl]
  );

  const openView = useCallback(
    (note: NoteWithLinks) => {
      queryClient.setQueryData(getGetNoteQueryKey(note.id), note);
      wasOpenedByPush.current = true;
      setNoteId(note.id, false);
    },
    [queryClient, setNoteId]
  );

  const closeView = useCallback(() => {
    if (wasOpenedByPush.current && syncToUrl) {
      wasOpenedByPush.current = false;
      window.history.back();
    } else {
      setNoteId(undefined, true);
    }
  }, [setNoteId, syncToUrl]);

  const currentNoteIndex =
    viewingNoteId === null ? -1 : allNotes.findIndex((note) => note.id === viewingNoteId);

  // Seed the detail cache like openView so navigation renders instantly, and
  // replace the history entry so Back closes the modal instead of stepping
  // through every viewed note.
  const handleModalNavigate = useCallback(
    (newIndex: number) => {
      const note = allNotes[newIndex]!;
      queryClient.setQueryData(getGetNoteQueryKey(note.id), note);
      setNoteId(note.id, true);
    },
    [allNotes, queryClient, setNoteId]
  );

  return {
    openCreate: () => setEditorOpen(true),
    openView,
    editorOpen,
    closeEditor: () => setEditorOpen(false),
    viewingNoteId,
    closeView,
    currentNoteIndex,
    totalCount: allNotes.length,
    handleModalNavigate,
  };
};
