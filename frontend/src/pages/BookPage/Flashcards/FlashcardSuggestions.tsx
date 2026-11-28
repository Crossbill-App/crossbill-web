import type { FlashcardSuggestionItem } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { FlashcardSuggestionCard } from '@/pages/BookPage/Flashcards/FlashcardSuggestionCard.tsx';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface FlashcardSuggestionsProps {
  suggestions: FlashcardSuggestionItem[];
  isLoading: boolean;
  onAcceptSuggestion: (suggestion: FlashcardSuggestionItem, index: number) => void;
  onRejectSuggestion: (index: number) => void;
}

export const FlashcardSuggestions = ({
  suggestions,
  isLoading,
  onAcceptSuggestion,
  onRejectSuggestion,
}: FlashcardSuggestionsProps) => {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (suggestions.length === 0) return null;

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2" gutterBottom sx={{ color: 'text.secondary' }}>
        {t('flashcards.aiSuggestions.title')}
      </Typography>
      <CardList>
        {suggestions.map((suggestion, index) => (
          <li key={index}>
            <FlashcardSuggestionCard
              question={suggestion.question}
              answer={suggestion.answer}
              onAccept={() => onAcceptSuggestion(suggestion, index)}
              onReject={() => onRejectSuggestion(index)}
            />
          </li>
        ))}
      </CardList>
    </Box>
  );
};
