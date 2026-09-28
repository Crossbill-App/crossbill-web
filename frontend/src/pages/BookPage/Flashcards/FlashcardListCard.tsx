import { useDeleteFlashcard } from '@/api/generated/flashcards/flashcards.ts';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { FlashcardCard } from '@/pages/BookPage/Flashcards/FlashcardCard.tsx';
import { NoteViewDialog } from '@/pages/BookPage/Notes/NoteViewDialog.tsx';
import { DeleteIcon, EditIcon, NotesIcon } from '@/theme/Icons.tsx';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export interface FlashcardListCardProps {
  flashcard: FlashcardWithContext;
  bookId: number;
  onEdit: () => void;
  showSourceHighlight?: boolean;
  /**
   * The note whose section is rendering this card. Cards reached from elsewhere
   * name their own note via `flashcard.note_id`.
   */
  noteId?: number;
}

export const FlashcardListCard = ({
  flashcard,
  bookId,
  onEdit,
  showSourceHighlight = true,
  noteId,
}: FlashcardListCardProps) => {
  const { t } = useTranslation();
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [isViewingNote, setIsViewingNote] = useState(false);
  const linkedNoteId =
    flashcard.note_id != null && flashcard.note_id !== noteId ? flashcard.note_id : null;
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();

  const deleteMutation = useDeleteFlashcard({
    mutation: {
      onSuccess: () => {
        cache.flashcardsChanged(bookId, noteId ?? flashcard.note_id ?? undefined);
      },
      onError: mutationErrorHandler(t('flashcards.errors.delete')),
    },
  });

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirmOpen(true);
  };

  const handleViewNoteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsViewingNote(true);
  };

  const handleConfirmDelete = async () => {
    setDeleteConfirmOpen(false);
    setIsDeleting(true);
    try {
      await deleteMutation.mutateAsync({ flashcardId: flashcard.id });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <FlashcardCard
        question={flashcard.question}
        answer={flashcard.answer}
        showSourceHighlight={showSourceHighlight}
        sourceHighlightText={flashcard.highlight?.text}
        renderActions={() => (
          <>
            {linkedNoteId != null && (
              <IconButtonWithTooltip
                label={t('flashcards.actions.viewLinkedNote')}
                onClick={handleViewNoteClick}
                disabled={isDeleting}
                icon={<NotesIcon fontSize="small" />}
              />
            )}
            <IconButtonWithTooltip
              label={t('flashcards.actions.edit')}
              onClick={onEdit}
              disabled={isDeleting}
              icon={<EditIcon fontSize="small" />}
            />
            <IconButtonWithTooltip
              label={t('flashcards.actions.delete')}
              onClick={handleDeleteClick}
              disabled={isDeleting}
              icon={<DeleteIcon fontSize="small" />}
            />
          </>
        )}
      />

      <ConfirmationDialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={handleConfirmDelete}
        message={t('flashcards.listCard.deleteConfirm')}
        confirmText={t('common.actions.delete')}
        confirmColor="error"
        isLoading={isDeleting}
      />

      {isViewingNote && linkedNoteId != null && (
        <NoteViewDialog noteId={linkedNoteId} onClose={() => setIsViewingNote(false)} />
      )}
    </>
  );
};
