import type { FlashcardReviewRequestRating } from '@/api/generated/model';
import { isTextEntry } from '@/utils/isTextEntry.ts';
import { useEffect, useEffectEvent } from 'react';

export const GRADES: readonly { key: string; rating: FlashcardReviewRequestRating }[] = [
  { key: '1', rating: 'again' },
  { key: '2', rating: 'hard' },
  { key: '3', rating: 'good' },
  { key: '4', rating: 'easy' },
];

interface ReviewKeyHandlers {
  enabled: boolean;
  revealed: boolean;
  onReveal: () => void;
  onGrade: (rating: FlashcardReviewRequestRating) => void;
}

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
      return;
    }

    const grade = GRADES.find(({ key }) => key === event.key);
    if (revealed && grade) {
      event.preventDefault();
      onGrade(grade.rating);
    }
  });

  useEffect(() => {
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
};
