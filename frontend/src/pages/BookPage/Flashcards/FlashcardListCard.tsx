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
      onError: mutationErrorHandler('delete flashcard'),
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
                title="View note"
                ariaLabel="View linked note"
                onClick={handleViewNoteClick}
                disabled={isDeleting}
                icon={<NotesIcon fontSize="small" />}
              />
            )}
            <IconButtonWithTooltip
              title="Edit"
              ariaLabel="Edit flashcard"
              onClick={onEdit}
              disabled={isDeleting}
              icon={<EditIcon fontSize="small" />}
            />
            <IconButtonWithTooltip
              title="Delete"
              ariaLabel="Delete flashcard"
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
        title="Delete Flashcard"
        message="Are you sure you want to delete this flashcard?"
        confirmText="Delete"
        confirmColor="error"
        isLoading={isDeleting}
      />

      {isViewingNote && linkedNoteId != null && (
        <NoteViewDialog noteId={linkedNoteId} onClose={() => setIsViewingNote(false)} />
      )}
    </>
  );
};
