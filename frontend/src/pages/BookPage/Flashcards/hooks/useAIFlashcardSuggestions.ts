import type {
  CollectionResponseFlashcardSuggestionItem,
  FlashcardSuggestionItem,
} from '@/api/generated/model';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export interface SuggestionsResult {
  data?: CollectionResponseFlashcardSuggestionItem;
  error: unknown;
}

export const useAIFlashcardSuggestions = (refetch?: () => Promise<SuggestionsResult>) => {
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<FlashcardSuggestionItem[]>([]);

  const fetchSuggestions = async () => {
    if (!refetch) return;
    setIsLoading(true);
    try {
      const { data, error } = await refetch();
      if (error) throw error;
      if (data?.items) {
        setSuggestions(data.items);
      }
    } catch (error) {
      console.error('Failed to fetch flashcard suggestions:', error);
      showSnackbar(t('common.errors.fetchFlashcardSuggestions'), 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const removeSuggestion = (index: number) => {
    setSuggestions((prev) => prev.filter((_, i) => i !== index));
  };

  return { canSuggest: !!refetch, isLoading, suggestions, fetchSuggestions, removeSuggestion };
};
