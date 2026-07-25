import type { Highlight } from '@/api/generated/model';
import { scrollToElementWithHighlight } from '@/components/animations/scrollUtils.ts';
import {
  useUrlEntityDialog,
  type UrlEntityDialogController,
} from '@/components/dialogs/useUrlEntityDialog.ts';
import { useCallback } from 'react';

interface UseHighlightDialogOptions {
  allHighlights: Highlight[];
  isMobile: boolean;
  syncToUrl?: boolean;
}

export interface HighlightDialogController extends Omit<
  UrlEntityDialogController<Highlight>,
  'close'
> {
  close: (lastViewedHighlightId?: number) => void;
}

export const useHighlightDialog = ({
  allHighlights,
  isMobile,
  syncToUrl = true,
}: UseHighlightDialogOptions): HighlightDialogController => {
  const dialog = useUrlEntityDialog<Highlight>({
    param: 'highlightId',
    items: allHighlights,
    syncToUrl,
  });

  const { close: closeDialog } = dialog;

  const close = useCallback(
    (lastViewedHighlightId?: number) => {
      closeDialog();

      if (lastViewedHighlightId && isMobile && syncToUrl) {
        scrollToElementWithHighlight(`highlight-${lastViewedHighlightId}`);
      }
    },
    [closeDialog, isMobile, syncToUrl]
  );

  return { ...dialog, close };
};
