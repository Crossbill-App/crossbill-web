import type { NoteWithLinks } from '@/api/generated/model';
import { getGetNoteQueryKey } from '@/api/generated/notes/notes.ts';
import {
  useUrlEntityDialog,
  type UrlEntityDialogController,
} from '@/components/dialogs/useUrlEntityDialog.ts';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

interface UseNoteDialogsOptions {
  syncToUrl?: boolean;
  /** Ordered notes for prev/next navigation in the view dialog (e.g. the filtered list). */
  allNotes?: NoteWithLinks[];
}

export interface NoteDialogsController extends Omit<
  UrlEntityDialogController<NoteWithLinks>,
  'open'
> {
  openView: (note: NoteWithLinks) => void;
  editorOpen: boolean;
  openCreate: () => void;
  closeEditor: () => void;
}

export const useNoteDialogs = (options: UseNoteDialogsOptions = {}): NoteDialogsController => {
  const { syncToUrl = true, allNotes = [] } = options;
  const queryClient = useQueryClient();

  // The create editor is not URL-synced
  const [editorOpen, setEditorOpen] = useState(false);

  const dialog = useUrlEntityDialog<NoteWithLinks>({
    param: 'noteId',
    items: allNotes,
    syncToUrl,
  });

  const { open, navigateToIndex, ...rest } = dialog;

  const openView = useCallback(
    (note: NoteWithLinks) => {
      queryClient.setQueryData(getGetNoteQueryKey(note.id), note);
      open(note.id);
    },
    [open, queryClient]
  );

  // Seed the detail cache like openView so navigation renders instantly; the
  // underlying navigation replaces the history entry so Back closes the dialog
  // instead of stepping through every viewed note.
  const handleNavigate = useCallback(
    (newIndex: number) => {
      const note = allNotes[newIndex];
      queryClient.setQueryData(getGetNoteQueryKey(note.id), note);
      navigateToIndex(newIndex);
    },
    [allNotes, navigateToIndex, queryClient]
  );

  return {
    ...rest,
    navigateToIndex: handleNavigate,
    openView,
    editorOpen,
    openCreate: () => setEditorOpen(true),
    closeEditor: () => setEditorOpen(false),
  };
};
