import type { NoteUpdateRequestKind, NoteWithLinks } from '@/api/generated/model';
import { useCreateNote, useDeleteNote, useUpdateNote } from '@/api/generated/notes/notes.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { GistHelperText } from '@/pages/BookPage/Notes/GistHelperText.tsx';
import { Box, ButtonBase, TextField, Typography } from '@mui/material';
import { find } from 'lodash';
import { useRef, useState, type KeyboardEvent } from 'react';

const PLACEHOLDER = 'What was this chapter about?';

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

  // The text on screen while a save is in flight; `null` means the server's
  // value is what is shown.
  const [draft, setDraft] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  // Set by Escape so the blur it causes does not save the reverted text.
  const cancelled = useRef(false);

  useResetOnChange([chapterId], () => {
    setDraft(null);
    setIsEditing(false);
    setSaveFailed(false);
  });

  // Once the refetched note carries the draft, the server value takes over —
  // dropping the draft any earlier would flash the old body on screen.
  useResetOnChange([savedBody], () => {
    if (!isEditing) setDraft(null);
  });

  const value = draft ?? savedBody;

  const failed = (action: string) => (error: unknown) => {
    mutationErrorHandler(action)(error);
    setSaveFailed(true);
    setIsEditing(true);
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

  const commit = () => {
    setIsEditing(false);
    if (value === savedBody) return;

    if (value.trim() === '') {
      if (gist) deleteMutation.mutate({ noteId: gist.id });
      else setDraft(null);
      return;
    }

    if (gist) {
      // A full replace: everything but the body is carried over, so a gist that
      // was given tags or extra chapters in the note dialog keeps them.
      updateMutation.mutate({
        noteId: gist.id,
        data: {
          title: gist.title,
          body: value,
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
          body: value,
          kind: 'gist',
          chapter_ids: [chapterId],
          highlight_ids: [],
          tag_ids: [],
        },
      });
    }
  };

  const handleBlur = () => {
    if (cancelled.current) {
      cancelled.current = false;
      return;
    }
    commit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      // Blur rather than save directly, so the save happens once whether the
      // reader finishes with Enter or by clicking away.
      event.preventDefault();
      (event.target as HTMLElement).blur();
    } else if (event.key === 'Escape') {
      // The chapter dialog closes on Escape; reverting the field is what this
      // Escape means.
      event.stopPropagation();
      cancelled.current = true;
      setDraft(null);
      setIsEditing(false);
    }
  };

  return (
    <Box sx={{ px: 2, mb: 2 }}>
      <Typography variant="body1" sx={{ fontWeight: 600, color: 'primary.main', py: 1.5 }}>
        Gist
      </Typography>
      {gist && !isEditing ? (
        <ButtonBase
          onClick={() => setIsEditing(true)}
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
            {value}
          </Typography>
        </ButtonBase>
      ) : (
        <TextField
          fullWidth
          multiline
          minRows={2}
          size="small"
          autoFocus={isEditing}
          error={saveFailed}
          placeholder={PLACEHOLDER}
          value={value}
          onChange={(event) => {
            cancelled.current = false;
            setDraft(event.target.value);
          }}
          onFocus={() => setIsEditing(true)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          helperText={
            <GistHelperText
              length={value.length}
              message={saveFailed ? 'Not saved — try again.' : undefined}
            />
          }
        />
      )}
    </Box>
  );
};
