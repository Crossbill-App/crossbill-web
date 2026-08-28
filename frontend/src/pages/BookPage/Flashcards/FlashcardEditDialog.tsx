import { useUpdateFlashcard } from '@/api/generated/flashcards/flashcards.ts';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { HighlightContent } from '@/pages/BookPage/common/HighlightContent.tsx';
import { Box, Button, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';

import { useGetNote } from '@/api/generated/notes/notes.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { NoteCard } from '@/pages/BookPage/Notes/NoteCard.tsx';
import { NoteViewDialog } from '@/pages/BookPage/Notes/NoteViewDialog.tsx';
import type { FlashcardFormValues } from './CreateFlashcardForm.tsx';

interface FlashcardEditDialogProps {
  flashcard: FlashcardWithContext;
  bookId: number;
  open: boolean;
  onClose: () => void;
}

export const FlashcardEditDialog = ({
  flashcard,
  bookId,
  open,
  onClose,
}: FlashcardEditDialogProps) => {
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const [isViewingNote, setIsViewingNote] = useState(false);

  const {
    control,
    handleSubmit,
    reset,
    formState: { isDirty, isValid },
  } = useForm<FlashcardFormValues>({
    mode: 'onChange',
    defaultValues: { question: flashcard.question, answer: flashcard.answer },
  });

  // Re-seed the fields when the edited card changes.
  useEffect(() => {
    reset({ question: flashcard.question, answer: flashcard.answer });
  }, [flashcard, reset]);

  const updateMutation = useUpdateFlashcard({
    mutation: {
      onSuccess: () => {
        cache.flashcardsChanged(bookId, flashcard.note_id ?? undefined);
        onClose();
      },
      onError: mutationErrorHandler('update flashcard'),
    },
  });

  const { data: noteData } = useGetNote(flashcard.note_id ?? 0, {
    query: {
      enabled: !!flashcard.note_id,
    },
  });

  const isSaving = updateMutation.isPending;

  const onSubmit = async (values: FlashcardFormValues) => {
    await updateMutation.mutateAsync({
      flashcardId: flashcard.id,
      data: {
        question: values.question.trim(),
        answer: values.answer.trim(),
      },
    });
  };

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      title="Edit Flashcard"
      maxWidth="md"
      isLoading={isSaving}
      footerActions={
        <Box sx={{ display: 'flex', gap: 1, width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSubmit(onSubmit)}
            disabled={!isDirty || !isValid || isSaving}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </Button>
        </Box>
      }
    >
      <Box sx={{ pt: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
        {flashcard.highlight && <HighlightContent highlight={flashcard.highlight} />}
        {noteData && (
          <NoteCard
            note={noteData}
            onClick={() => {
              setIsViewingNote(true);
            }}
          />
        )}

        <Box>
          <Typography
            variant="caption"
            sx={{
              color: 'primary.main',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              display: 'block',
              mb: 1,
            }}
          >
            Question
          </Typography>
          <RHFTextField
            name="question"
            control={control}
            rules={{ validate: (value) => value.trim().length > 0 || 'Question is required' }}
            fullWidth
            multiline
            minRows={2}
            maxRows={4}
            placeholder="Enter your question..."
            disabled={isSaving}
          />
        </Box>

        <Box>
          <Typography
            variant="caption"
            sx={{
              color: 'secondary.main',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              display: 'block',
              mb: 1,
            }}
          >
            Answer
          </Typography>
          <RHFTextField
            name="answer"
            control={control}
            rules={{ validate: (value) => value.trim().length > 0 || 'Answer is required' }}
            fullWidth
            multiline
            minRows={3}
            maxRows={6}
            placeholder="Enter your answer..."
            disabled={isSaving}
          />
        </Box>
      </Box>

      {isViewingNote && noteData != null && (
        <NoteViewDialog noteId={noteData.id} onClose={() => setIsViewingNote(false)} />
      )}
    </CommonDialog>
  );
};
