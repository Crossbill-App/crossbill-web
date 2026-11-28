import type { FlashcardReviewRequestRating } from '@/api/generated/model';
import { useEffect, useEffectEvent } from 'react';

export const GRADE_KEYS: Record<string, FlashcardReviewRequestRating> = {
  '1': 'again',
  '2': 'hard',
  '3': 'good',
  '4': 'easy',
};

interface ReviewKeyHandlers {
  enabled: boolean;
  revealed: boolean;
  onReveal: () => void;
  onGrade: (rating: FlashcardReviewRequestRating) => void;
}

const isTextEntry = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));

const isControl = (target: EventTarget | null) =>
  target instanceof HTMLElement && target.closest('button, a, [role="button"]') !== null;

/** Space or Enter shows the answer, and 1 to 4 grade it. A focused control keeps Space and Enter for itself. */
export const useReviewKeys = ({ enabled, revealed, onReveal, onGrade }: ReviewKeyHandlers) => {
  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (!enabled || event.defaultPrevented || event.repeat) return;
    if (event.altKey || event.ctrlKey || event.metaKey || isTextEntry(event.target)) return;

    if (!revealed && (event.key === ' ' || event.key === 'Enter')) {
      if (isControl(event.target)) return;
      event.preventDefault();
      onReveal();
    } else if (revealed && event.key in GRADE_KEYS) {
      event.preventDefault();
      onGrade(GRADE_KEYS[event.key]);
    }
  });

  useEffect(() => {
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
};
