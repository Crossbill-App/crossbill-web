import { useCancelJobBatch, useGetJobBatch } from '@/api/generated/jobs/jobs';
import type { JobBatchResponse } from '@/api/generated/model';
import { useSnackbar } from '@/context/SnackbarContext';
import { useCallback, useEffect, useRef, useState } from 'react';

const TERMINAL_STATUSES = ['completed', 'completed_with_errors', 'failed', 'cancelled'];
const POLL_INTERVAL = 3000;

function isTerminal(status: string | undefined): boolean {
  return !!status && TERMINAL_STATUSES.includes(status);
}

interface UseJobBatchProgressOptions {
  /**
   * The batch already running when the page loaded, from the feature's own
   * "active batch" query. Tracking resumes from it, so a refresh mid-run does
   * not lose the progress display.
   */
  activeBatch: JobBatchResponse | null | undefined;
  /** The batch reached a terminal status. Fires once per batch. */
  onFinished: (batch: JobBatchResponse) => void;
  onCancelled: () => void;
}

interface JobBatchProgress {
  batch: JobBatchResponse | undefined;
  isActive: boolean;
  /** Follow a batch that was just enqueued. */
  track: (batchId: number) => void;
  cancel: () => void;
}

/**
 * Follows one job batch from enqueued to terminal: polls it, reports the
 * outcome once, and cancels it on request.
 *
 * Starting a batch is deliberately not part of this — each feature enqueues
 * through its own endpoint, with its own arguments and response shape — so a
 * caller passes the new batch's id to `track` from its own mutation.
 */
export const useJobBatchProgress = ({
  activeBatch,
  onFinished,
  onCancelled,
}: UseJobBatchProgressOptions): JobBatchProgress => {
  const { showSnackbar } = useSnackbar();
  const [batchId, setBatchId] = useState<number | null>(null);
  // Batches whose outcome has already been reported. Without this, a stale
  // "active batch" response would restart tracking on a batch that just ended,
  // and it is also what makes the effects below safe to re-run: a caller may
  // pass fresh callbacks on every render without its outcome firing twice.
  const settledIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!activeBatch || isTerminal(activeBatch.status) || activeBatch.id === settledIdRef.current) {
      return;
    }
    setBatchId((current) => current ?? activeBatch.id);
  }, [activeBatch]);

  const { data: batch } = useGetJobBatch(batchId ?? 0, {
    query: {
      enabled: batchId !== null,
      refetchInterval: (query) => (isTerminal(query.state.data?.status) ? false : POLL_INTERVAL),
    },
  });

  useEffect(() => {
    if (!batch || !isTerminal(batch.status) || settledIdRef.current === batch.id) {
      return;
    }
    settledIdRef.current = batch.id;
    setBatchId(null);
    onFinished(batch);
  }, [batch, onFinished]);

  const { mutate: cancelBatch } = useCancelJobBatch({
    mutation: {
      onSuccess: (cancelled) => {
        settledIdRef.current = cancelled.id;
        setBatchId(null);
        onCancelled();
      },
      onError: () => {
        showSnackbar('Failed to cancel batch.', 'error');
      },
    },
  });

  const cancel = useCallback(() => {
    if (batchId !== null) {
      cancelBatch({ batchId });
    }
  }, [cancelBatch, batchId]);

  return {
    batch,
    isActive: batchId !== null && !isTerminal(batch?.status),
    track: setBatchId,
    cancel,
  };
};
