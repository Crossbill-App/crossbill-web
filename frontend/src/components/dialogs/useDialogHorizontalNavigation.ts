import { useCallback, useMemo } from 'react';

/**
 * Everything a previous/next control needs, or `undefined` when there is
 * nothing to page between. One object so the dialog shell and the beside-the-
 * content arrows are wired from the same value rather than five loose props
 * restated at each dialog.
 */
export interface DialogNavigation {
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}

interface UseDialogHorizontalNavigationOptions {
  currentIndex: number;
  totalCount: number;
  onNavigate?: (newIndex: number) => void;
}

/**
 * Paging between sibling entities in a detail modal: the flags and callbacks
 * its previous/next controls render from. Hand the result to `CommonDialog`,
 * which owns the arrow keys that do the same thing from the keyboard.
 *
 * Deliberately no swipe gesture. A horizontal drag anywhere in the dialog used
 * to page the whole modal, which put it in competition with every horizontally
 * scrollable thing inside one — carousels most of all, where the gesture to
 * scroll a strip is exactly the gesture to leave the entity it belongs to. The
 * controls are explicit instead: one pair of arrows in the dialog's footer, in
 * the same place at every width.
 */
export const useDialogHorizontalNavigation = ({
  currentIndex,
  totalCount,
  onNavigate,
}: UseDialogHorizontalNavigationOptions) => {
  const hasNavigation = totalCount > 1 && onNavigate;
  const hasPrevious = hasNavigation && currentIndex > 0;
  const hasNext = hasNavigation && currentIndex < totalCount - 1;

  const handlePrevious = useCallback(() => {
    if (hasPrevious) {
      onNavigate!(currentIndex - 1);
    }
  }, [currentIndex, hasPrevious, onNavigate]);

  const handleNext = useCallback(() => {
    if (hasNext) {
      onNavigate!(currentIndex + 1);
    }
  }, [currentIndex, hasNext, onNavigate]);

  const navigation: DialogNavigation | undefined = useMemo(
    () =>
      hasNavigation
        ? {
            hasPrevious: !!hasPrevious,
            hasNext: !!hasNext,
            onPrevious: handlePrevious,
            onNext: handleNext,
          }
        : undefined,
    [hasNavigation, hasPrevious, hasNext, handlePrevious, handleNext]
  );

  return { hasNavigation, navigation };
};
