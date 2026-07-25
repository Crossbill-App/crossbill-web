import type { TagInBook } from '@/api/generated/model';
import { useAddTagToHighlight, useRemoveTagFromHighlight } from '@/api/generated/tags/tags.ts';
import { useBookMutationHelpers } from '@/hooks/useBookMutationHelpers.ts';
import { filter, map } from 'lodash';
import { useEffect, useState } from 'react';

export interface UseImmediateTagMutationParams {
  /** Book ID for API calls */
  bookId: number;
  /** Highlight ID for API calls */
  highlightId: number;
  /** Initial tags for the highlight */
  initialTags: TagInBook[];
}

export interface UseImmediateTagMutationReturn {
  /** Whether a mutation is currently processing */
  isProcessing: boolean;
  /** Current list of tags */
  currentTags: TagInBook[];
  /** Function to update the tag list - handles add/remove mutations */
  updateTagList: (newValue: (TagInBook | string)[]) => Promise<void>;
}

const calculateAddedTags = (current: string[], updated: string[]): string[] => {
  return filter(updated, (name) => !current.includes(name));
};

const calculateRemovedTags = (current: TagInBook[], updated: string[]): TagInBook[] => {
  return filter(current, (tag) => !updated.includes(tag.name));
};

/**
 * Hook for managing immediate tag mutations on highlights
 * Handles adding and removing tags with optimistic updates and error handling
 *
 * @param params - Configuration for the hook
 * @returns Object with processing state, current tags, and update function
 *
 * @example
 * ```tsx
 * const { isProcessing, currentTags, updateTagList } = useImmediateTagMutation({
 *   bookId: 1,
 *   highlightId: 123,
 *   initialTags: highlight.tags,
 *   showSnackbar,
 * });
 * ```
 */
export const useImmediateTagMutation = ({
  bookId,
  highlightId,
  initialTags,
}: UseImmediateTagMutationParams): UseImmediateTagMutationReturn => {
  const { mutationErrorHandler, invalidateBookAndTags } = useBookMutationHelpers(bookId);
  const [currentTags, setCurrentTags] = useState<TagInBook[]>(initialTags);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    setCurrentTags(initialTags);
  }, [highlightId, initialTags]);

  const addTagMutation = useAddTagToHighlight({
    mutation: {
      onSuccess: (data: { tags: TagInBook[] }) => {
        setCurrentTags(data.tags);
        invalidateBookAndTags();
      },
      onError: mutationErrorHandler('add tag'),
    },
  });

  const removeTagMutation = useRemoveTagFromHighlight({
    mutation: {
      onSuccess: (data: { tags: TagInBook[] }) => {
        setCurrentTags(data.tags);
        invalidateBookAndTags();
      },
      onError: mutationErrorHandler('remove tag'),
    },
  });

  const addTagToHighlight = async (tagName: string) => {
    setIsProcessing(true);
    try {
      await addTagMutation.mutateAsync({
        bookId,
        highlightId,
        data: { name: tagName },
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const removeTagFromHighlight = async (tagId: number) => {
    setIsProcessing(true);
    try {
      await removeTagMutation.mutateAsync({
        bookId,
        highlightId,
        tagId,
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const updateTagList = async (newValue: (TagInBook | string)[]) => {
    const currentTagNames = map(currentTags, (t) => t.name);
    const newTagNames = map(newValue, (v) => (typeof v === 'string' ? v : v.name));

    const addedTags = calculateAddedTags(currentTagNames, newTagNames);
    const removedTags = calculateRemovedTags(currentTags, newTagNames);

    for (const tagName of addedTags) {
      await addTagToHighlight(tagName);
    }

    for (const tag of removedTags) {
      await removeTagFromHighlight(tag.id);
    }
  };

  return {
    isProcessing,
    currentTags,
    updateTagList,
  };
};
