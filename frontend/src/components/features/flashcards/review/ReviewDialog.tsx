import {
  useRecordFlashcardReview,
  useSetFlashcardStatus,
} from '@/api/generated/flashcards/flashcards.ts';
import type { FlashcardReviewRequestRating } from '@/api/generated/model';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { CommonDialogTitle } from '@/components/dialogs/CommonDialogTitle.tsx';
import { ProgressBar } from '@/components/dialogs/ProgressBar.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { FlashcardDialog } from '@/pages/BookPage/Flashcards/FlashcardDialog.tsx';
import { tabularNums } from '@/theme/theme.ts';
import { Alert, Box, Button, Typography } from '@mui/material';
import type { AxiosError } from 'axios';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ReviewCard } from './ReviewCard.tsx';
import { useReviewKeys } from './useReviewKeys.ts';
import { useReviewQueue, type QueuedFlashcard } from './useReviewQueue.ts';

const hasLeftReview = (error: unknown) =>
  [404, 409].includes((error as AxiosError).response?.status ?? 0);

const AllCaughtUp = () => {
  const { t } = useTranslation();

  return (
    <Box sx={{ textAlign: 'center', pt: 4 }}>
      <Typography variant="sectionTitle" component="h2">
        {t('review.done.title')}
      </Typography>
      <EmptyStateText variant="page">{t('review.done.message')}</EmptyStateText>
    </Box>
  );
};

interface ReviewDialogProps {
  /** Only this book's due flashcards; every book's when left out. */
  bookId?: number;
  onClose: () => void;
}

export const ReviewDialog = ({ bookId, onClose }: ReviewDialogProps) => {
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const queue = useReviewQueue(bookId);
  const { current } = queue;
  const [revealedId, setRevealedId] = useState<number | null>(null);
  const [editing, setEditing] = useState<QueuedFlashcard | null>(null);
  const revealed = current !== null && revealedId === current.id;

  const restoreUnlessGone = (flashcardId: number, error: unknown) => {
    if (!hasLeftReview(error)) queue.restore(flashcardId);
  };

  const recordReview = useRecordFlashcardReview({
    mutation: {
      onError: (error, { flashcardId }) => {
        restoreUnlessGone(flashcardId, error);
        mutationErrorHandler(t('review.errors.grade'))(error);
      },
    },
  });

  const setStatus = useSetFlashcardStatus({
    mutation: {
      onSuccess: (flashcard) => {
        cache.flashcardsChanged(flashcard.book_id, flashcard.note_id ?? undefined);
        if (flashcard.status === 'active') {
          queue.restore(flashcard.id);
          return;
        }
        showSnackbar(t('review.suspended.message'), 'info', {
          label: t('review.suspended.undo'),
          onClick: () =>
            setStatus.mutate({ flashcardId: flashcard.id, data: { status: 'active' } }),
        });
      },
      onError: (error, { flashcardId, data }) => {
        const suspending = data.status === 'suspended';
        if (suspending) restoreUnlessGone(flashcardId, error);
        mutationErrorHandler(t(suspending ? 'review.errors.suspend' : 'review.errors.unsuspend'))(
          error
        );
      },
    },
  });

  const grade = (rating: FlashcardReviewRequestRating) => {
    if (!current) return;
    queue.remove(current.id);
    recordReview.mutate({
      flashcardId: current.id,
      data: { rating, reviewed_at: new Date().toISOString() },
    });
  };

  const suspend = () => {
    if (!current) return;
    queue.remove(current.id);
    setStatus.mutate({ flashcardId: current.id, data: { status: 'suspended' } });
  };

  const reveal = () => {
    if (current) setRevealedId(current.id);
  };

  const close = () => {
    cache.dueFlashcardsReviewed();
    onClose();
  };

  useReviewKeys({
    enabled: current !== null && editing === null,
    revealed,
    onReveal: reveal,
    onGrade: grade,
  });

  const body = () => {
    if (queue.isLoadError) {
      return (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={queue.retry}>
              {t('common.actions.tryAgain')}
            </Button>
          }
        >
          {t('review.dialog.loadError')}
        </Alert>
      );
    }
    if (queue.isDone) return <AllCaughtUp />;
    if (!current) return <Spinner />;

    return (
      <ReviewCard
        key={current.id}
        card={current}
        revealed={revealed}
        onReveal={reveal}
        onGrade={grade}
        onEdit={() => setEditing(current)}
        onSuspend={suspend}
      />
    );
  };

  return (
    <CommonDialog
      open
      onClose={close}
      headerElement={
        queue.total > 0 && (
          <ProgressBar
            currentIndex={Math.min(queue.position, queue.total) - 1}
            totalCount={queue.total}
          />
        )
      }
      title={
        <CommonDialogTitle>
          {t('review.dialog.title')}
          {current && (
            <Typography
              component="span"
              variant="body2"
              sx={{ ml: 2, color: 'text.secondary', ...tabularNums }}
            >
              {t('review.dialog.position', { position: queue.position, total: queue.total })}
            </Typography>
          )}
        </CommonDialogTitle>
      }
      footerActions={
        queue.isDone && (
          <Button variant="contained" onClick={close}>
            {t('common.actions.done')}
          </Button>
        )
      }
    >
      <Box sx={{ py: 3 }}>{body()}</Box>

      {editing && (
        <FlashcardDialog
          bookId={editing.book_id}
          target={{ mode: 'edit', flashcard: { ...editing, highlight: null } }}
          onClose={() => setEditing(null)}
          onDeleted={() => queue.remove(editing.id)}
        />
      )}
    </CommonDialog>
  );
};
