import {
  useCancelJobBatch,
  useEnqueueBookDigest,
  useGetActiveBookDigestBatch,
  useGetJobBatch,
} from '@/api/generated/jobs/jobs';
import type { JobBatchResponse } from '@/api/generated/model';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { AIFeature } from '@/components/features/AIFeature';
import { useSnackbar } from '@/context/SnackbarContext';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { AIIcon, CloseIcon } from '@/theme/Icons';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useCallback, useRef, useState } from 'react';

interface BatchDigestToolbarProps {
  bookId: number;
}

const TERMINAL_STATUSES = ['completed', 'completed_with_errors', 'failed', 'cancelled'];
const POLL_INTERVAL = 3000;

function isTerminal(status: string | undefined): boolean {
  return !!status && TERMINAL_STATUSES.includes(status);
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
  const [batchId, setBatchId] = useState<number | null>(null);
  const handledTerminalRef = useRef<number | null>(null);

  // Check for an already-active batch on mount (survives page refresh)
  useGetActiveBookDigestBatch(bookId, {
    query: {
      select: (response: JobBatchResponse | null) => {
        if (response && !isTerminal(response.status) && batchId === null) {
          queueMicrotask(() => {
            setBatchId(response.id);
          });
        }
        return response;
      },
    },
  });

  const { mutate: enqueue, isPending: isEnqueuing } = useEnqueueBookDigest({
    mutation: {
      onSuccess: (response) => {
        handledTerminalRef.current = null;
        setBatchId(response.id);
      },
      onError: () => {
        showSnackbar('Failed to start batch generation.', 'error');
      },
    },
  });

  const { data: batch } = useGetJobBatch(batchId ?? 0, {
    query: {
      enabled: batchId !== null,
      refetchInterval: (query) => {
        const status = query.state.data?.status;
        if (isTerminal(status)) return false;
        return POLL_INTERVAL;
      },
      select: (response: JobBatchResponse) => {
        if (isTerminal(response.status) && handledTerminalRef.current !== response.id) {
          handledTerminalRef.current = response.id;

          cache.digestBatchFinished(bookId);

          showCompletionMessage(response, showSnackbar);

          queueMicrotask(() => {
            setBatchId(null);
          });
        }
        return response;
      },
    },
  });

  const { mutate: cancelBatch } = useCancelJobBatch({
    mutation: {
      onSuccess: () => {
        showSnackbar('Batch generation cancelled.', 'info');
        cache.digestBatchCancelled(bookId);
        setBatchId(null);
      },
      onError: () => {
        showSnackbar('Failed to cancel batch.', 'error');
      },
    },
  });

  const isActive = batchId !== null && (!batch || !isTerminal(batch.status));

  const handleEnqueue = useCallback(() => {
    enqueue({ bookId });
  }, [enqueue, bookId]);

  const handleCancel = useCallback(() => {
    if (batchId) {
      cancelBatch({ batchId });
    }
  }, [cancelBatch, batchId]);

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
            onClick={handleCancel}
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
