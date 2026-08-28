import type { NoteUpdateRequestKind, NoteWithLinks } from '@/api/generated/model';
import { useCreateNote, useDeleteNote, useUpdateNote } from '@/api/generated/notes/notes.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useCommitOnBlur } from '@/hooks/useCommitOnBlur.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { GistHelperText } from '@/pages/BookPage/Notes/GistHelperText.tsx';
import { Box, ButtonBase, TextField, Typography } from '@mui/material';
import { find } from 'lodash';
import { useState } from 'react';

const PLACEHOLDER = 'What was this chapter about?';

interface ExistingGistTextProps {
  text: string;
  onEdit: () => void;
}

const ExistingGistText = ({ text, onEdit }: ExistingGistTextProps) => (
  <ButtonBase
    onClick={onEdit}
    sx={{
      width: '100%',
      justifyContent: 'flex-start',
      textAlign: 'left',
      borderRadius: 1,
      px: 1,
      py: 0.5,
      '&:hover': { bgcolor: 'action.hover' },
    }}
  >
    <Typography sx={{ fontStyle: 'italic' }} variant="body1">
      {text}
    </Typography>
  </ButtonBase>
);

interface ChapterGistSectionProps {
  chapterId: number;
  chapterName: string;
  notes: NoteWithLinks[];
}

export const ChapterGistSection = ({ chapterId, chapterName, notes }: ChapterGistSectionProps) => {
  const { book } = useBookPage();
  const cache = useCacheEvents();
  const { showSnackbar } = useSnackbar();
  const mutationErrorHandler = useMutationErrorHandler();

  const gist = find(notes, (note) => note.kind === 'gist') ?? null;
  const savedBody = gist?.body ?? '';

  const [isEditing, setIsEditing] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);

  const field = useCommitOnBlur({
    saved: savedBody,
    onCommit: (body) => save(body),
    onBlur: () => setIsEditing(false),
    onCancel: () => setIsEditing(false),
  });

  useResetOnChange([chapterId], () => {
    field.revert();
    setIsEditing(false);
    setSaveFailed(false);
  });

  const failed = (action: string) => (error: unknown) => {
    mutationErrorHandler(action)(error);
    setSaveFailed(true);
    setIsEditing(true);
    // The save never landed, so leaving the field again should retry it.
    field.allowRecommit();
  };

  const saved = () => {
    setSaveFailed(false);
    cache.noteChanged(book.id, gist?.id);
  };

  const createMutation = useCreateNote({
    mutation: { onSuccess: saved, onError: failed('save gist') },
  });
  const updateMutation = useUpdateNote({
    mutation: { onSuccess: saved, onError: failed('save gist') },
  });
  const deleteMutation = useDeleteNote({
    mutation: {
      onSuccess: (_data, variables) => {
        cache.noteDeleted(book.id, variables.noteId);
        showSnackbar('Gist deleted.', 'info');
      },
      onError: failed('delete gist'),
    },
  });

  function save(body: string) {
    if (body.trim() === '') {
      if (gist) deleteMutation.mutate({ noteId: gist.id });
      else field.revert();
      return;
    }

    if (gist) {
      // A full replace: everything but the body is carried over, so a gist that
      // was given tags or extra chapters in the note dialog keeps them.
      updateMutation.mutate({
        noteId: gist.id,
        data: {
          title: gist.title,
          body,
          kind: gist.kind as NoteUpdateRequestKind,
          chapter_ids: gist.chapter_ids,
          highlight_ids: gist.highlight_ids,
          tag_ids: gist.tag_ids,
        },
      });
    } else {
      createMutation.mutate({
        data: {
          book_id: book.id,
          title: chapterName,
          body,
          kind: 'gist',
          chapter_ids: [chapterId],
          highlight_ids: [],
          tag_ids: [],
        },
      });
    }
  }

  return (
    <Box sx={{ px: 2, mb: 2 }}>
      <Typography variant="body1" sx={{ fontWeight: 600, color: 'primary.main', py: 1.5 }}>
        Gist
      </Typography>
      {gist && !isEditing ? (
        <ExistingGistText text={field.value} onEdit={() => setIsEditing(true)} />
      ) : (
        <TextField
          fullWidth
          multiline
          minRows={2}
          size="small"
          autoFocus={isEditing}
          error={saveFailed}
          placeholder={PLACEHOLDER}
          {...field.inputProps}
          helperText={
            <GistHelperText
              length={field.value.length}
              message={saveFailed ? 'Not saved — try again.' : undefined}
            />
          }
        />
      )}
    </Box>
  );
};
