import { useUpdateHighlightLabel } from '@/api/generated/highlight-labels/highlight-labels.ts';
import type { HighlightLabelUpdate } from '@/api/generated/model';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import type { SaveStatusHandle } from '@/hooks/useSaveStatus.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';

export interface HighlightLabelSave {
  /** True while a save is in flight, so a field can decline to start a second. */
  isSaving: boolean;
  /** Writes one edit to a highlighter's label and drives the marker beside the field. */
  save: (styleId: number, data: HighlightLabelUpdate) => void;
}

export const useHighlightLabelSave = (
  bookId: number,
  saveStatus: SaveStatusHandle
): HighlightLabelSave => {
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();

  const mutation = useUpdateHighlightLabel({
    mutation: {
      onSuccess: () => {
        saveStatus.saved();
        cache.highlightLabelsChanged(bookId);
      },
      onError: (error: unknown) => {
        saveStatus.reset();
        mutationErrorHandler('update label')(error);
      },
    },
  });

  return {
    isSaving: mutation.isPending,
    save: (styleId, data) => {
      saveStatus.saving();
      mutation.mutate({ styleId, data });
    },
  };
};
