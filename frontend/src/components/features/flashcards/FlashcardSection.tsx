import type { FlashcardSuggestionItem } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import {
  CreateFlashcardForm,
  type FlashcardFormValues,
} from '@/pages/BookPage/Flashcards/CreateFlashcardForm.tsx';
import { FlashcardListCard } from '@/pages/BookPage/Flashcards/FlashcardListCard.tsx';
import { FlashcardSuggestions } from '@/pages/BookPage/Flashcards/FlashcardSuggestions.tsx';
import { Box, Typography } from '@mui/material';
import { useState } from 'react';

/**
 * Source-agnostic flashcard section for entity view modals (highlights, notes).
 * Renders the existing cards, a manual create/edit form and AI suggestions;
 * the caller wires the source-specific data and mutations.
 */
interface FlashcardSectionProps {
  /** Existing cards, pre-mapped and pre-sorted by the caller. */
  flashcards: FlashcardWithContext[];
  bookId: number;
  disabled?: boolean;
  isProcessing: boolean;
  /** Creates a card; resolves true on success (form is cleared only then). */
  onSaveFlashcard: (question: string, answer: string) => Promise<boolean>;
  /** Updates a card; resolves true on success. */
  onUpdateFlashcard: (flashcardId: number, question: string, answer: string) => Promise<boolean>;
  suggestions: FlashcardSuggestionItem[];
  suggestionsLoading: boolean;
  onFetchSuggestions: () => Promise<void>;
  onRemoveSuggestion: (index: number) => void;
  /** Query keys to invalidate when a card is deleted, in addition to book details. */
  /** Set when the cards belong to a note, whose detail embeds its own card list. */
  noteId?: number;
}

interface FlashcardsListProps {
  flashcardsWithContext: FlashcardWithContext[];
  bookId: number;
  onEdit: (flashcardId: number) => void;
  /** Set when the cards belong to a note, whose detail embeds its own card list. */
  noteId?: number;
}

const FlashcardsList = ({ flashcardsWithContext, bookId, onEdit, noteId }: FlashcardsListProps) => {
  if (flashcardsWithContext.length === 0) {
    return null;
  }

  return (
    <CardList sx={{ mb: 2 }}>
      {flashcardsWithContext.map((flashcard) => (
        <li key={flashcard.id}>
          <FlashcardListCard
            flashcard={flashcard}
            bookId={bookId}
            onEdit={() => onEdit(flashcard.id)}
            showSourceHighlight={false}
            noteId={noteId}
          />
        </li>
      ))}
    </CardList>
  );
};

export const FlashcardSection = ({
  flashcards,
  bookId,
  disabled = false,
  isProcessing,
  onSaveFlashcard,
  onUpdateFlashcard,
  suggestions,
  suggestionsLoading,
  onFetchSuggestions,
  onRemoveSuggestion,
  noteId,
}: FlashcardSectionProps) => {
  const [editingFlashcardId, setEditingFlashcardId] = useState<number | null>(null);

  const editingFlashcard =
    editingFlashcardId != null ? flashcards.find((f) => f.id === editingFlashcardId) : undefined;

  const handleSave = async (values: FlashcardFormValues) => {
    const saved = editingFlashcardId
      ? await onUpdateFlashcard(editingFlashcardId, values.question, values.answer)
      : await onSaveFlashcard(values.question, values.answer);
    if (saved) setEditingFlashcardId(null);
    return saved;
  };

  const handleCancelEdit = () => {
    setEditingFlashcardId(null);
  };

  const handleAcceptSuggestion = async (suggestion: FlashcardSuggestionItem, index: number) => {
    const saved = await onSaveFlashcard(suggestion.question, suggestion.answer);
    if (saved) {
      onRemoveSuggestion(index);
    }
  };

  return (
    <Box>
      <Typography
        variant="subtitle2"
        gutterBottom
        sx={{
          color: 'text.secondary',
        }}
      >
        Flashcards
      </Typography>

      <FlashcardsList
        flashcardsWithContext={flashcards}
        bookId={bookId}
        onEdit={setEditingFlashcardId}
        noteId={noteId}
      />

      <CreateFlashcardForm
        key={editingFlashcardId ?? 'new'}
        editingFlashcardId={editingFlashcardId}
        initialValues={
          editingFlashcard
            ? { question: editingFlashcard.question, answer: editingFlashcard.answer }
            : undefined
        }
        isDisabled={disabled || isProcessing}
        isProcessing={isProcessing}
        onSave={handleSave}
        onCancelEdit={handleCancelEdit}
      />

      <AIFeature>
        <FlashcardSuggestions
          suggestions={suggestions}
          isLoading={suggestionsLoading}
          disabled={disabled}
          onFetchSuggestions={() => void onFetchSuggestions()}
          onAcceptSuggestion={(suggestion, index) => void handleAcceptSuggestion(suggestion, index)}
          onRejectSuggestion={onRemoveSuggestion}
        />
      </AIFeature>
    </Box>
  );
};
