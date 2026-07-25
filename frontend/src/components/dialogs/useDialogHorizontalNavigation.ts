import { useCallback, useEffect, useRef } from 'react';
import { useSwipeable } from 'react-swipeable';

// Module-level stack to track active navigation dialogs.
// Only the topmost dialog should handle keyboard navigation.
let activeNavigationStack: symbol[] = [];

interface UseDialogHorizontalNavigationOptions {
  open: boolean;
  currentIndex: number;
  totalCount: number;
  onNavigate?: (newIndex: number) => void;
}

export const useDialogSwipeNavigation = ({
  currentIndex,
  totalCount,
  onNavigate,
}: Omit<UseDialogHorizontalNavigationOptions, 'open'>) => {
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

  const swipeHandlers = useSwipeable({
    onSwipedLeft: () => {
      if (hasNext) handleNext();
    },
    onSwipedRight: () => {
      if (hasPrevious) handlePrevious();
    },
    swipeDuration: 500,
    preventScrollOnSwipe: false,
  });

  return {
    swipeHandlers,
  };
};

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

  // Register/unregister this dialog on the navigation stack
  useEffect(() => {
    if (!open || !hasNavigation) return;

    const id = idRef.current;
    activeNavigationStack.push(id);
    return () => {
      activeNavigationStack = activeNavigationStack.filter((s) => s !== id);
    };
  }, [open, hasNavigation]);

  // Keyboard navigation
  useEffect(() => {
    if (!open || !hasNavigation) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Only respond to keyboard events if this is the topmost navigation dialog
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

  const { swipeHandlers } = useDialogSwipeNavigation({
    currentIndex,
    totalCount,
    onNavigate,
  });

  return {
    hasNavigation,
    hasPrevious,
    hasNext,
    handlePrevious,
    handleNext,
    swipeHandlers,
  };
};
