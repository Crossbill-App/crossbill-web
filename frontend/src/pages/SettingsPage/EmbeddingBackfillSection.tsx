import type { JobBatchResponse } from '@/api/generated/model';
import { useBackfillEmbeddings, useGetActiveBackfill } from '@/api/generated/semantic/semantic';
import { AIActionButton } from '@/components/buttons/AIActionButton';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useSnackbar } from '@/context/SnackbarContext';
import { useJobBatchProgress } from '@/hooks/useJobBatchProgress';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { CloseIcon } from '@/theme/Icons';
import { Box, CircularProgress, Typography } from '@mui/material';
import type { AxiosError } from 'axios';

type ShowSnackbar = ReturnType<typeof useSnackbar>['showSnackbar'];

function reportOutcome(batch: JobBatchResponse, showSnackbar: ShowSnackbar) {
  if (batch.status === 'completed') {
    showSnackbar('Library indexed.', 'success');
  } else if (batch.status === 'completed_with_errors') {
    showSnackbar(
      `Indexed ${batch.completed_jobs}/${batch.total_jobs} items. Some failed.`,
      'warning'
    );
  } else if (batch.status === 'failed') {
    showSnackbar('Indexing failed.', 'error');
  }
}

/**
 * Starts and follows the library-wide embedding backfill.
 *
 * The run outlives the page, so the active-batch query is what the display is
 * built from: arriving mid-run shows the progress of a batch this page never
 * started.
 */
export const EmbeddingBackfillSection = () => {
  const cache = useCacheEvents();
  const { showSnackbar } = useSnackbar();
  const { data: activeBatch } = useGetActiveBackfill();

  const { batch, isActive, track, cancel } = useJobBatchProgress({
    activeBatch,
    onFinished: (finished) => {
      cache.embeddingBackfillChanged();
      reportOutcome(finished, showSnackbar);
    },
    onCancelled: () => {
      cache.embeddingBackfillChanged();
      showSnackbar('Indexing cancelled.', 'info');
    },
  });

  const { mutate: startBackfill, isPending: isStarting } = useBackfillEmbeddings({
    mutation: {
      onSuccess: (response) => {
        if (response.batch) {
          track(response.batch.id);
        } else {
          showSnackbar('Everything in your library is already indexed.', 'info');
        }
      },
      onError: (error) => {
        if ((error as AxiosError).response?.status === 409) {
          // Someone else's tab, or another device, got there first — refetch so
          // this page picks up the run it is being told about.
          cache.embeddingBackfillChanged();
          showSnackbar('Indexing is already in progress.', 'warning');
        } else {
          showSnackbar('Failed to start indexing.', 'error');
        }
      },
    },
  });

  const isBusy = isStarting || isActive;
  const done = batch ? batch.completed_jobs + batch.failed_jobs : 0;

  return (
    <Box sx={{ mt: 6 }}>
      <SectionTitle showDivider>Semantic search</SectionTitle>
      <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
        Index your library for semantic search. Only content that has not been embedded yet is
        processed.
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <AIActionButton
          text="Index library"
          disabled={isBusy}
          onClick={() => {
            // No `book_id`: the whole library.
            startBackfill({});
          }}
        />

        {isBusy && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={20} />
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {batch ? `Indexing (${done}/${batch.total_jobs})` : 'Starting...'}
            </Typography>
            <IconButtonWithTooltip label="Cancel indexing" onClick={cancel} icon={<CloseIcon />} />
          </Box>
        )}
      </Box>
    </Box>
  );
};
