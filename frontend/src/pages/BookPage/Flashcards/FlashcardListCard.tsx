import { useSetFlashcardStatus } from '@/api/generated/flashcards/flashcards.ts';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { FlashcardCard } from '@/pages/BookPage/Flashcards/FlashcardCard.tsx';
import { useFlashcardDeletion } from '@/pages/BookPage/Flashcards/hooks/useFlashcardDeletion.tsx';
import { NoteViewDialog } from '@/pages/BookPage/Notes/NoteViewDialog.tsx';
import { DeleteIcon, EditIcon, NotesIcon, UnsuspendIcon } from '@/theme/Icons.tsx';
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
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const [isViewingNote, setIsViewingNote] = useState(false);
  const isSuspended = flashcard.status === 'suspended';
  const linkedNoteId =
    flashcard.note_id != null && flashcard.note_id !== noteId ? flashcard.note_id : null;
  const owningNoteId = noteId ?? flashcard.note_id ?? undefined;
  const { requestDelete, isDeleting, confirmation } = useFlashcardDeletion({
    bookId,
    noteId: owningNoteId,
  });
  const unsuspend = useSetFlashcardStatus({
    mutation: {
      onSuccess: () => cache.flashcardsChanged(bookId, owningNoteId),
      onError: mutationErrorHandler(t('flashcards.errors.unsuspend')),
    },
  });
  const isBusy = isDeleting || unsuspend.isPending;

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    requestDelete(flashcard.id);
  };

  const handleViewNoteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsViewingNote(true);
  };

  return (
    <>
      <FlashcardCard
        question={flashcard.question}
        answer={flashcard.answer}
        showSourceHighlight={showSourceHighlight}
        sourceHighlightText={flashcard.highlight?.text}
        suspended={isSuspended}
        renderActions={() => (
          <>
            {isSuspended && (
              <IconButtonWithTooltip
                label={t('flashcards.actions.unsuspend')}
                onClick={(e) => {
                  e.stopPropagation();
                  unsuspend.mutate({ flashcardId: flashcard.id, data: { status: 'active' } });
                }}
                disabled={isBusy}
                icon={<UnsuspendIcon fontSize="small" />}
              />
            )}
            {linkedNoteId != null && (
              <IconButtonWithTooltip
                label={t('flashcards.actions.viewLinkedNote')}
                onClick={handleViewNoteClick}
                disabled={isBusy}
                icon={<NotesIcon fontSize="small" />}
              />
            )}
            <IconButtonWithTooltip
              label={t('flashcards.actions.edit')}
              onClick={onEdit}
              disabled={isBusy}
              icon={<EditIcon fontSize="small" />}
            />
            <IconButtonWithTooltip
              label={t('flashcards.actions.delete')}
              onClick={handleDeleteClick}
              disabled={isBusy}
              icon={<DeleteIcon fontSize="small" />}
            />
          </>
        )}
      />

      {confirmation}

      {isViewingNote && linkedNoteId != null && (
        <NoteViewDialog noteId={linkedNoteId} onClose={() => setIsViewingNote(false)} />
      )}
    </>
  );
};
