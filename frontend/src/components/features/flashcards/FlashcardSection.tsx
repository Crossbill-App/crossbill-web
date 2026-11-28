import type { FlashcardSuggestionItem } from '@/api/generated/model';
import { AIActionButton } from '@/components/buttons/AIActionButton';
import { CardList } from '@/components/CardList.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import {
  FlashcardDialog,
  type FlashcardDialogTarget,
} from '@/pages/BookPage/Flashcards/FlashcardDialog.tsx';
import { FlashcardListCard } from '@/pages/BookPage/Flashcards/FlashcardListCard.tsx';
import { FlashcardSuggestions } from '@/pages/BookPage/Flashcards/FlashcardSuggestions.tsx';
import {
  useAIFlashcardSuggestions,
  type SuggestionsResult,
} from '@/pages/BookPage/Flashcards/hooks/useAIFlashcardSuggestions.ts';
import {
  sourceNoteId,
  useCreateFlashcard,
  type FlashcardSource,
} from '@/pages/BookPage/Flashcards/hooks/useCreateFlashcard.ts';
import { AddIcon } from '@/theme/Icons.tsx';
import { Box, Button } from '@mui/material';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface FlashcardSectionProps {
  flashcards: FlashcardWithContext[];
  bookId: number;
  /** Where a card made here is filed. */
  source: FlashcardSource;
  disabled?: boolean;
  /** Omitted where the surface has nothing to suggest from. */
  fetchSuggestions?: () => Promise<SuggestionsResult>;
}

const noSuggestions = () => Promise.resolve({ error: null });

/** The Flashcards tab of the highlight, note and chapter dialogs. */
export const FlashcardSection = ({
  flashcards,
  bookId,
  source,
  disabled = false,
  fetchSuggestions,
}: FlashcardSectionProps) => {
  const { t } = useTranslation();
  const [dialogTarget, setDialogTarget] = useState<FlashcardDialogTarget | null>(null);
  const { createFlashcard } = useCreateFlashcard(bookId);
  const {
    isLoading,
    suggestions,
    fetchSuggestions: suggest,
    removeSuggestion,
  } = useAIFlashcardSuggestions(fetchSuggestions ?? noSuggestions);

  const handleAcceptSuggestion = async (suggestion: FlashcardSuggestionItem, index: number) => {
    if (await createFlashcard(source, suggestion)) removeSuggestion(index);
  };

  return (
    <Box>
      {flashcards.length === 0 ? (
        <EmptyStateText>{t('flashcards.section.empty')}</EmptyStateText>
      ) : (
        <CardList>
          {flashcards.map((flashcard) => (
            <li key={flashcard.id}>
              <FlashcardListCard
                flashcard={flashcard}
                bookId={bookId}
                onEdit={() => setDialogTarget({ mode: 'edit', flashcard })}
                showSourceHighlight={false}
                noteId={sourceNoteId(source)}
              />
            </li>
          ))}
        </CardList>
      )}

      <DialogToolbar sx={{ mt: 2 }}>
        {fetchSuggestions && suggestions.length === 0 && (
          <AIFeature>
            <AIActionButton
              text={t('flashcards.aiSuggestions.suggest')}
              onClick={() => void suggest()}
              disabled={disabled || isLoading}
              iconOnly
            />
          </AIFeature>
        )}
        <Button
          variant="outlined"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => setDialogTarget({ mode: 'create', source })}
          disabled={disabled}
        >
          {t('flashcards.actions.new')}
        </Button>
      </DialogToolbar>

      {fetchSuggestions && (
        <AIFeature>
          <FlashcardSuggestions
            suggestions={suggestions}
            isLoading={isLoading}
            onAcceptSuggestion={(suggestion, index) =>
              void handleAcceptSuggestion(suggestion, index)
            }
            onRejectSuggestion={removeSuggestion}
          />
        </AIFeature>
      )}

      {dialogTarget && (
        <FlashcardDialog
          bookId={bookId}
          target={dialogTarget}
          onClose={() => setDialogTarget(null)}
        />
      )}
    </Box>
  );
};
