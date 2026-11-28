import { useDeleteFlashcard, useUpdateFlashcard } from '@/api/generated/flashcards/flashcards.ts';
import { useGetNote } from '@/api/generated/notes/notes.ts';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { HighlightContent } from '@/pages/BookPage/common/HighlightContent.tsx';
import { NoteCard } from '@/pages/BookPage/Notes/NoteCard.tsx';
import { NoteViewDialog } from '@/pages/BookPage/Notes/NoteViewDialog.tsx';
import { DeleteIcon } from '@/theme/Icons.tsx';
import { Box, Button } from '@mui/material';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import {
  sourceNoteId,
  useCreateFlashcard,
  type FlashcardContent,
  type FlashcardSource,
} from './hooks/useCreateFlashcard.ts';

export type FlashcardDialogTarget =
  { mode: 'create'; source: FlashcardSource } | { mode: 'edit'; flashcard: FlashcardWithContext };

interface FlashcardDialogProps {
  bookId: number;
  target: FlashcardDialogTarget;
  onClose: () => void;
}

const sourceHighlight = (target: FlashcardDialogTarget) => {
  if (target.mode === 'edit') return target.flashcard.highlight;
  return target.source.kind === 'highlight' ? target.source.highlight : null;
};

const linkedNoteId = (target: FlashcardDialogTarget) =>
  target.mode === 'edit' ? (target.flashcard.note_id ?? undefined) : sourceNoteId(target.source);

export const FlashcardDialog = ({ bookId, target, onClose }: FlashcardDialogProps) => {
  const { t } = useTranslation();
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const [isViewingNote, setIsViewingNote] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const editing = target.mode === 'edit' ? target.flashcard : null;
  const highlight = sourceHighlight(target);
  const noteId = linkedNoteId(target);

  const {
    control,
    handleSubmit,
    formState: { isDirty, isValid },
  } = useForm<FlashcardContent>({
    mode: 'onChange',
    defaultValues: editing
      ? { question: editing.question, answer: editing.answer }
      : { question: '', answer: '' },
  });

  const { createFlashcard, isPending: isCreating } = useCreateFlashcard(bookId);

  const onChanged = () => {
    cache.flashcardsChanged(bookId, noteId);
    onClose();
  };

  const updateMutation = useUpdateFlashcard({
    mutation: {
      onSuccess: onChanged,
      onError: mutationErrorHandler(t('flashcards.errors.update')),
    },
  });

  const deleteMutation = useDeleteFlashcard({
    mutation: {
      onSuccess: onChanged,
      onError: mutationErrorHandler(t('flashcards.errors.delete')),
    },
  });

  const { data: note } = useGetNote(noteId ?? 0, { query: { enabled: noteId !== undefined } });

  const isSaving = isCreating || updateMutation.isPending || deleteMutation.isPending;

  const onSubmit = async (values: FlashcardContent) => {
    if (target.mode === 'create') {
      if (await createFlashcard(target.source, values)) onClose();
      return;
    }
    updateMutation.mutate({
      flashcardId: target.flashcard.id,
      data: { question: values.question.trim(), answer: values.answer.trim() },
    });
  };

  const handleConfirmDelete = () => {
    setDeleteConfirmOpen(false);
    if (editing) deleteMutation.mutate({ flashcardId: editing.id });
  };

  const required = (message: string) => (value: string) => value.trim().length > 0 || message;

  return (
    <CommonDialog
      open
      onClose={onClose}
      title={editing ? t('flashcards.actions.edit') : t('flashcards.actions.new')}
      maxWidth="md"
      isLoading={isSaving}
      footerActions={
        <Box sx={{ display: 'flex', gap: 1, width: '100%' }}>
          {editing && (
            <Button
              color="error"
              startIcon={<DeleteIcon />}
              onClick={() => setDeleteConfirmOpen(true)}
              disabled={isSaving}
            >
              {t('common.actions.delete')}
            </Button>
          )}
          <Box sx={{ flex: 1 }} />
          <Button onClick={onClose} disabled={isSaving}>
            {t('common.actions.cancel')}
          </Button>
          <Button
            variant="contained"
            onClick={handleSubmit(onSubmit)}
            disabled={!isDirty || !isValid || isSaving}
          >
            {isSaving ? t('common.status.saving') : t('common.actions.save')}
          </Button>
        </Box>
      }
    >
      <Box sx={{ pt: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
        {highlight && <HighlightContent highlight={highlight} />}
        {note && <NoteCard note={note} onClick={() => setIsViewingNote(true)} />}

        <RHFTextField
          name="question"
          control={control}
          rules={{ validate: required(t('flashcards.dialog.validation.questionRequired')) }}
          label={t('flashcards.fields.question')}
          fullWidth
          multiline
          minRows={2}
          maxRows={4}
          disabled={isSaving}
        />
        <RHFTextField
          name="answer"
          control={control}
          rules={{ validate: required(t('flashcards.dialog.validation.answerRequired')) }}
          label={t('flashcards.fields.answer')}
          fullWidth
          multiline
          minRows={3}
          maxRows={6}
          disabled={isSaving}
        />
      </Box>

      <ConfirmationDialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={handleConfirmDelete}
        message={t('flashcards.shared.deleteConfirm')}
        confirmText={t('common.actions.delete')}
        confirmColor="error"
        isLoading={deleteMutation.isPending}
      />

      {isViewingNote && note && (
        <NoteViewDialog noteId={note.id} onClose={() => setIsViewingNote(false)} />
      )}
    </CommonDialog>
  );
};
