import { useCallback, useEffect, useMemo, useRef } from 'react';

// Module-level stack to track active navigation dialogs.
// Only the topmost dialog should handle keyboard navigation.
let activeNavigationStack: symbol[] = [];

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
  open: boolean;
  currentIndex: number;
  totalCount: number;
  onNavigate?: (newIndex: number) => void;
}

/**
 * Paging between sibling entities in a detail modal: arrow keys, plus the
 * flags its previous/next controls render from.
 *
 * Deliberately no swipe gesture. A horizontal drag anywhere in the dialog used
 * to page the whole modal, which put it in competition with every horizontally
 * scrollable thing inside one — carousels most of all, where the gesture to
 * scroll a strip is exactly the gesture to leave the entity it belongs to. The
 * controls are explicit instead: arrows in the footer on mobile, beside the
 * content on wider screens.
 */
export const useDialogHorizontalNavigation = ({
  open,
  currentIndex,
  totalCount,
  onNavigate,
}: UseDialogHorizontalNavigationOptions) => {
  const hasNavigation = totalCount > 1 && onNavigate;
  const hasPrevious = hasNavigation && currentIndex > 0;
  const hasNext = hasNavigation && currentIndex < totalCount - 1;

  const idRef = useRef(Symbol());

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

  // Register/unregister this dialog on the navigation stack. Every open dialog
  // registers, whether or not it has navigation of its own: a modal with no
  // navigation content (e.g. a note viewed on its own, not from a paged list)
  // must still shadow the dialogs beneath it, or their arrow-key listener
  // stays "topmost" and pages a dialog the user can't even see.
  useEffect(() => {
    if (!open) return;

    const id = idRef.current;
    activeNavigationStack.push(id);
    return () => {
      activeNavigationStack = activeNavigationStack.filter((s) => s !== id);
    };
  }, [open]);

  // Keyboard navigation
  useEffect(() => {
    if (!open || !hasNavigation) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Only respond to keyboard events if this is the topmost dialog on the
      // stack, navigation-capable or not.
      if (activeNavigationStack[activeNavigationStack.length - 1] !== idRef.current) return;

      const target = e.target as HTMLElement;

      // Don't navigate when user is typing in an input field
      const isEditableElement =
        target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;

      // Don't navigate when user is interacting with element inside area which is marked as to prevent
      // navigation by the special attribute
      const isInPreventNavigationArea = target.closest('[data-prevent-navigation="true"]');

      if (isEditableElement || isInPreventNavigationArea) return;

      if (e.key === 'ArrowLeft' && hasPrevious) {
        e.preventDefault();
        handlePrevious();
      } else if (e.key === 'ArrowRight' && hasNext) {
        e.preventDefault();
        handleNext();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, hasNavigation, hasPrevious, hasNext, handlePrevious, handleNext]);

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
