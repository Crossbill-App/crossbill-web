import { useGetDueFlashcards } from '@/api/generated/flashcards/flashcards.ts';
import { ReviewDialog } from '@/components/features/flashcards/review/ReviewDialog.tsx';
import { ReviewIcon } from '@/theme/Icons.tsx';
import { Button } from '@mui/material';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export const ReviewButton = ({ bookId }: { bookId: number }) => {
  const { t } = useTranslation();
  const [isReviewing, setIsReviewing] = useState(false);
  const { data } = useGetDueFlashcards({ book_id: bookId, limit: 1 });
  const dueCount = data?.total ?? 0;

  return (
    <>
      {dueCount > 0 && (
        <Button startIcon={<ReviewIcon />} onClick={() => setIsReviewing(true)}>
          {t('review.actions.open', { count: dueCount })}
        </Button>
      )}
      {isReviewing && <ReviewDialog bookId={bookId} onClose={() => setIsReviewing(false)} />}
    </>
  );
};
