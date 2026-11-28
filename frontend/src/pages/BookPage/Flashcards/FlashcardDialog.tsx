import { useUpdateFlashcard } from '@/api/generated/flashcards/flashcards.ts';
import type { Flashcard, Highlight } from '@/api/generated/model';
import { useGetNote } from '@/api/generated/notes/notes.ts';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { HighlightContent, HighlightQuote } from '@/pages/BookPage/common/HighlightContent.tsx';
import { NoteContent } from '@/pages/BookPage/Notes/NoteCard.tsx';
import { DeleteIcon } from '@/theme/Icons.tsx';
import { Box, Button } from '@mui/material';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import {
  sourceNoteId,
  useCreateFlashcard,
  type FlashcardContent,
  type FlashcardSource,
} from './hooks/useCreateFlashcard.ts';
import { useFlashcardDeletion } from './hooks/useFlashcardDeletion.tsx';

interface EditedFlashcard extends Flashcard {
  highlight?: Highlight | null;
  highlight_text?: string | null;
}

export type FlashcardDialogTarget =
  { mode: 'create'; source: FlashcardSource } | { mode: 'edit'; flashcard: EditedFlashcard };

interface FlashcardDialogProps {
  bookId: number;
  target: FlashcardDialogTarget;
  onClose: () => void;
  onDeleted?: () => void;
}

const sourceHighlight = (target: FlashcardDialogTarget) => {
  if (target.mode === 'edit') return target.flashcard.highlight ?? null;
  return target.source.kind === 'highlight' ? target.source.highlight : null;
};

const sourceHighlightText = (target: FlashcardDialogTarget) =>
  target.mode === 'edit' ? (target.flashcard.highlight_text ?? null) : null;

const required = (message: string) => (value: string) => value.trim().length > 0 || message;

const linkedNoteId = (target: FlashcardDialogTarget) =>
  target.mode === 'edit' ? (target.flashcard.note_id ?? undefined) : sourceNoteId(target.source);

export const FlashcardDialog = ({ bookId, target, onClose, onDeleted }: FlashcardDialogProps) => {
  const { t } = useTranslation();
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const editing = target.mode === 'edit' ? target.flashcard : null;
  const highlight = sourceHighlight(target);
  const highlightText = sourceHighlightText(target);
  const noteId = linkedNoteId(target);

  const {
    control,
    handleSubmit,
    formState: { isDirty, isValid },
  } = useForm<FlashcardContent>({
    mode: 'onChange',
    defaultValues: { question: editing?.question ?? '', answer: editing?.answer ?? '' },
  });

  const { createFlashcard, isPending: isCreating } = useCreateFlashcard(bookId);

  const updateMutation = useUpdateFlashcard({
    mutation: {
      onSuccess: () => {
        cache.flashcardsChanged(bookId, noteId);
        onClose();
      },
      onError: mutationErrorHandler(t('flashcards.errors.update')),
    },
  });

  const { requestDelete, isDeleting, confirmation } = useFlashcardDeletion({
    bookId,
    noteId,
    onDeleted: () => {
      onDeleted?.();
      onClose();
    },
  });

  const { data: note } = useGetNote(noteId ?? 0, { query: { enabled: noteId !== undefined } });

  const isSaving = isCreating || updateMutation.isPending || isDeleting;

  const onSubmit = async (values: FlashcardContent) => {
    const content = { question: values.question.trim(), answer: values.answer.trim() };
    if (target.mode === 'edit') {
      updateMutation.mutate({ flashcardId: target.flashcard.id, data: content });
    } else if (await createFlashcard(target.source, content)) {
      onClose();
    }
  };

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
              onClick={() => requestDelete(editing.id)}
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
        {!highlight && highlightText && <HighlightQuote text={highlightText} />}
        {note && <NoteContent note={note} />}

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

      {confirmation}
    </CommonDialog>
  );
};
