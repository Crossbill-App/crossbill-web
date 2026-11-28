import type { FlashcardSuggestionItem } from '@/api/generated/model';
import { AIActionButton } from '@/components/buttons/AIActionButton';
import { CardList } from '@/components/CardList.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { AddIcon } from '@/theme/Icons.tsx';
import { Box, Button } from '@mui/material';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FlashcardDialog, type FlashcardDialogTarget } from './FlashcardDialog.tsx';
import { FlashcardListCard } from './FlashcardListCard.tsx';
import { FlashcardSuggestions } from './FlashcardSuggestions.tsx';
import {
  useAIFlashcardSuggestions,
  type SuggestionsResult,
} from './hooks/useAIFlashcardSuggestions.ts';
import {
  sourceNoteId,
  useCreateFlashcard,
  type FlashcardSource,
} from './hooks/useCreateFlashcard.ts';

interface FlashcardSectionProps {
  flashcards: FlashcardWithContext[];
  bookId: number;
  source: FlashcardSource;
  disabled?: boolean;
  refetchSuggestions?: () => Promise<SuggestionsResult>;
}

export const FlashcardSection = ({
  flashcards,
  bookId,
  source,
  disabled = false,
  refetchSuggestions,
}: FlashcardSectionProps) => {
  const { t } = useTranslation();
  const [dialogTarget, setDialogTarget] = useState<FlashcardDialogTarget | null>(null);
  const { createFlashcard } = useCreateFlashcard(bookId);
  const { canSuggest, isLoading, suggestions, fetchSuggestions, removeSuggestion } =
    useAIFlashcardSuggestions(refetchSuggestions);

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
        {canSuggest && suggestions.length === 0 && (
          <AIFeature>
            <AIActionButton
              text={t('flashcards.aiSuggestions.suggest')}
              onClick={() => void fetchSuggestions()}
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

      {canSuggest && (
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
