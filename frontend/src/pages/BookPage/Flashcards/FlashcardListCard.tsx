import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { FlashcardCard } from '@/pages/BookPage/Flashcards/FlashcardCard.tsx';
import { useFlashcardDeletion } from '@/pages/BookPage/Flashcards/hooks/useFlashcardDeletion.tsx';
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
  const [isViewingNote, setIsViewingNote] = useState(false);
  const linkedNoteId =
    flashcard.note_id != null && flashcard.note_id !== noteId ? flashcard.note_id : null;
  const { requestDelete, isDeleting, confirmation } = useFlashcardDeletion({
    bookId,
    noteId: noteId ?? flashcard.note_id ?? undefined,
  });

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

      {confirmation}

      {isViewingNote && linkedNoteId != null && (
        <NoteViewDialog noteId={linkedNoteId} onClose={() => setIsViewingNote(false)} />
      )}
    </>
  );
};
