import { useDeleteFlashcard } from '@/api/generated/flashcards/flashcards.ts';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { useBookMutationHelpers } from '@/hooks/useBookMutationHelpers.ts';
import { FlashcardCard } from '@/pages/BookPage/Flashcards/FlashcardCard.tsx';
import { DeleteIcon, EditIcon } from '@/theme/Icons.tsx';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { useState } from 'react';

export interface FlashcardListCardProps {
  flashcard: FlashcardWithContext;
  bookId: number;
  onEdit: () => void;
  showSourceHighlight?: boolean;
  /** Query keys to invalidate on delete, in addition to the book details query. */
  additionalInvalidateKeys?: QueryKey[];
}

export const FlashcardListCard = ({
  flashcard,
  bookId,
  onEdit,
  showSourceHighlight = true,
  additionalInvalidateKeys = [],
}: FlashcardListCardProps) => {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const queryClient = useQueryClient();
  const { mutationErrorHandler, invalidateBookDetails } = useBookMutationHelpers(bookId);

  const deleteMutation = useDeleteFlashcard({
    mutation: {
      onSuccess: () => {
        invalidateBookDetails();
        for (const queryKey of additionalInvalidateKeys) {
          void queryClient.invalidateQueries({ queryKey });
        }
      },
      onError: mutationErrorHandler('delete flashcard'),
    },
  });

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirmOpen(true);
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
    </>
  );
};
