import type { FlashcardSuggestionItem } from '@/api/generated/model';
import { AIActionButton } from '@/components/buttons/AIActionButton';
import { CardList } from '@/components/CardList.tsx';
import { FlashcardSuggestionCard } from '@/pages/BookPage/Flashcards/FlashcardSuggestionCard.tsx';
import { Box, CircularProgress, Typography } from '@mui/material';

interface FlashcardSuggestionsProps {
  suggestions: FlashcardSuggestionItem[];
  isLoading: boolean;
  disabled: boolean;
  onFetchSuggestions: () => void;
  onAcceptSuggestion: (suggestion: FlashcardSuggestionItem, index: number) => void;
  onRejectSuggestion: (index: number) => void;
}

export const FlashcardSuggestions = ({
  suggestions,
  isLoading,
  disabled,
  onFetchSuggestions,
  onAcceptSuggestion,
  onRejectSuggestion,
}: FlashcardSuggestionsProps) => {
  return (
    <>
      {suggestions.length ? (
        <Typography
          variant="subtitle2"
          gutterBottom
          sx={{
            color: 'text.secondary',
          }}
        >
          Suggested flashcards
        </Typography>
      ) : (
        <AIActionButton
          text={'Suggest flashcards'}
          onClick={onFetchSuggestions}
          disabled={disabled || isLoading}
        />
      )}

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {!isLoading && suggestions.length > 0 && (
        <CardList sx={{ mb: 2 }}>
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
      )}
    </>
  );
};
