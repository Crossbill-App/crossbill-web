import type { NoteUpdateRequest, NoteWithLinks } from '@/api/generated/model';
import {
  getGetNoteQueryKey,
  getGetNotesForBookQueryKey,
  useUpdateNote,
} from '@/api/generated/notes/notes.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useBookMutationHelpers } from '@/hooks/useBookMutationHelpers.ts';
import { useQueryClient } from '@tanstack/react-query';

interface UseNoteLinksOptions {
  bookId: number;
}

interface MutateOptions {
  onSuccess?: () => void;
}

/**
 * Adds or removes a note's link to a highlight or chapter. There is no
 * dedicated link/unlink endpoint — links are replaced wholesale on note
 * update — so each operation re-sends the full note with the target id added
 * to or filtered out of the relevant array.
 */
export const useNoteLinks = ({ bookId }: UseNoteLinksOptions) => {
  const queryClient = useQueryClient();
  const { showSnackbar } = useSnackbar();
  const { mutationErrorHandler } = useBookMutationHelpers(bookId);

  const updateNoteMutation = useUpdateNote({
    mutation: {
      onSuccess: (_data, { noteId }) => {
        void queryClient.invalidateQueries({
          queryKey: getGetNotesForBookQueryKey(bookId),
        });
        void queryClient.invalidateQueries({
          queryKey: getGetNoteQueryKey(noteId),
        });
      },
      onError: mutationErrorHandler('update note links'),
    },
  });

  const updateLinks = (
    note: NoteWithLinks,
    links: Partial<NoteUpdateRequest>,
    successMessage: string,
    options?: MutateOptions
  ) => {
    const payload: NoteUpdateRequest = {
      title: note.title,
      body: note.body,
      kind: note.kind as NoteUpdateRequest['kind'],
      chapter_ids: note.chapter_ids,
      highlight_ids: note.highlight_ids,
      tag_ids: note.tag_ids,
      ...links,
    };
    updateNoteMutation.mutate(
      { noteId: note.id, data: payload },
      {
        onSuccess: () => {
          showSnackbar(successMessage, 'success');
          options?.onSuccess?.();
        },
      }
    );
  };

  const linkHighlight = (note: NoteWithLinks, highlightId: number, options?: MutateOptions) => {
    updateLinks(
      note,
      { highlight_ids: [...new Set([...note.highlight_ids, highlightId])] },
      'Highlight added to note.',
      options
    );
  };

  const unlinkHighlight = (note: NoteWithLinks, highlightId: number) => {
    updateLinks(
      note,
      { highlight_ids: note.highlight_ids.filter((id) => id !== highlightId) },
      'Link removed.'
    );
  };

  const linkChapter = (note: NoteWithLinks, chapterId: number, options?: MutateOptions) => {
    updateLinks(
      note,
      { chapter_ids: [...new Set([...note.chapter_ids, chapterId])] },
      'Chapter added to note.',
      options
    );
  };

  const unlinkChapter = (note: NoteWithLinks, chapterId: number) => {
    updateLinks(
      note,
      { chapter_ids: note.chapter_ids.filter((id) => id !== chapterId) },
      'Link removed.'
    );
  };

  return {
    linkHighlight,
    unlinkHighlight,
    linkChapter,
    unlinkChapter,
    isPending: updateNoteMutation.isPending,
  };
};
