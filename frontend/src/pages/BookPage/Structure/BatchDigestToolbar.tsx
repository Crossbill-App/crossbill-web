import { useEnqueueBookDigest, useGetActiveBookDigestBatch } from '@/api/generated/jobs/jobs';
import type { JobBatchResponse } from '@/api/generated/model';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { AIFeature } from '@/components/features/AIFeature';
import { useSnackbar } from '@/context/SnackbarContext';
import { useJobBatchProgress } from '@/hooks/useJobBatchProgress';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { AIIcon, CloseIcon } from '@/theme/Icons';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useCallback } from 'react';

interface BatchDigestToolbarProps {
  bookId: number;
}

function showCompletionMessage(
  batch: JobBatchResponse,
  showSnackbar: (msg: string, severity: 'error' | 'warning' | 'info' | 'success') => void
) {
  if (batch.status === 'completed') {
    showSnackbar('All chapter summaries generated.', 'success');
  } else if (batch.status === 'completed_with_errors') {
    showSnackbar(
      `Generated ${batch.completed_jobs}/${batch.total_jobs} summaries. Some chapters failed.`,
      'warning'
    );
  } else if (batch.status === 'failed') {
    showSnackbar('Batch generation failed.', 'error');
  }
}

export const BatchDigestToolbar = ({ bookId }: BatchDigestToolbarProps) => {
  const cache = useCacheEvents();
  const { showSnackbar } = useSnackbar();

  // An already-active batch, so the progress display survives a page refresh.
  const { data: activeBatch } = useGetActiveBookDigestBatch(bookId);

  const { batch, isActive, track, cancel } = useJobBatchProgress({
    activeBatch,
    onFinished: (finished) => {
      cache.digestBatchFinished(bookId);
      showCompletionMessage(finished, showSnackbar);
    },
    onCancelled: () => {
      cache.digestBatchCancelled(bookId);
      showSnackbar('Batch generation cancelled.', 'info');
    },
  });

  const { mutate: enqueue, isPending: isEnqueuing } = useEnqueueBookDigest({
    mutation: {
      onSuccess: (response) => {
        track(response.id);
      },
      onError: () => {
        showSnackbar('Failed to start batch generation.', 'error');
      },
    },
  });

  const handleEnqueue = useCallback(() => {
    enqueue({ bookId });
  }, [enqueue, bookId]);

  if (isEnqueuing || isActive) {
    const completed = batch ? batch.completed_jobs + batch.failed_jobs : 0;
    const total = batch?.total_jobs ?? 0;

    return (
      <AIFeature>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size={20} />
          <Typography
            variant="body2"
            sx={{
              color: 'text.secondary',
            }}
          >
            Generating summaries{total > 0 ? ` (${completed}/${total})` : '...'}
          </Typography>
          <IconButtonWithTooltip
            title="Cancel generation"
            onClick={cancel}
            ariaLabel="Cancel batch generation"
            icon={<CloseIcon />}
          />
        </Box>
      </AIFeature>
    );
  }

  return (
    <AIFeature>
      <IconButtonWithTooltip
        title="Generate summaries for all chapters"
        onClick={handleEnqueue}
        ariaLabel="Generate summaries for all chapters"
        icon={<AIIcon />}
      />
    </AIFeature>
  );
};
