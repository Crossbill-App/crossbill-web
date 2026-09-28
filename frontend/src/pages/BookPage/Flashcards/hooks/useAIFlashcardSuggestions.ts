import type {
  CollectionResponseFlashcardSuggestionItem,
  FlashcardSuggestionItem,
} from '@/api/generated/model';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Holds AI flashcard suggestion state for an entity view modal.
 * The fetcher is source-specific (highlight, note, ...) and provided by the caller.
 */
export const useAIFlashcardSuggestions = (
  fetchFn: () => Promise<CollectionResponseFlashcardSuggestionItem | undefined>
) => {
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<FlashcardSuggestionItem[]>([]);

  const fetchSuggestions = async () => {
    setIsLoading(true);
    try {
      const data = await fetchFn();
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

  return { isLoading, suggestions, fetchSuggestions, removeSuggestion };
};
