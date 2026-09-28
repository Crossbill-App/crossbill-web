import type { JobBatchResponse } from '@/api/generated/model';
import { useBackfillEmbeddings, useGetActiveBackfill } from '@/api/generated/semantic/semantic';
import { AIActionButton } from '@/components/buttons/AIActionButton';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useSnackbar } from '@/context/SnackbarContext';
import { useJobBatchProgress } from '@/hooks/useJobBatchProgress';
import { i18n } from '@/i18n';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { CloseIcon } from '@/theme/Icons';
import { Box, CircularProgress, Typography } from '@mui/material';
import type { AxiosError } from 'axios';
import { useTranslation } from 'react-i18next';

type ShowSnackbar = ReturnType<typeof useSnackbar>['showSnackbar'];

function reportOutcome(batch: JobBatchResponse, showSnackbar: ShowSnackbar) {
  if (batch.status === 'completed') {
    showSnackbar(i18n.t('settings.embeddingBackfill.completed'), 'success');
  } else if (batch.status === 'completed_with_errors') {
    showSnackbar(
      i18n.t('settings.embeddingBackfill.completedWithErrors', {
        completed: batch.completed_jobs,
        total: batch.total_jobs,
      }),
      'warning'
    );
  } else if (batch.status === 'failed') {
    showSnackbar(i18n.t('settings.embeddingBackfill.failed'), 'error');
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
  const { t } = useTranslation();
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
      showSnackbar(t('settings.embeddingBackfill.cancelled'), 'info');
    },
  });

  const { mutate: startBackfill, isPending: isStarting } = useBackfillEmbeddings({
    mutation: {
      onSuccess: (response) => {
        if (response.batch) {
          track(response.batch.id);
        } else {
          showSnackbar(t('settings.embeddingBackfill.alreadyIndexed'), 'info');
        }
      },
      onError: (error) => {
        if ((error as AxiosError).response?.status === 409) {
          // Someone else's tab, or another device, got there first — refetch so
          // this page picks up the run it is being told about.
          cache.embeddingBackfillChanged();
          showSnackbar(t('settings.embeddingBackfill.alreadyRunning'), 'warning');
        } else {
          showSnackbar(t('settings.embeddingBackfill.startFailed'), 'error');
        }
      },
    },
  });

  const isBusy = isStarting || isActive;
  const done = batch ? batch.completed_jobs + batch.failed_jobs : 0;

  return (
    <Box sx={{ mt: 6 }}>
      <SectionTitle showDivider>{t('settings.embeddingBackfill.title')}</SectionTitle>
      <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
        {t('settings.embeddingBackfill.description')}
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <AIActionButton
          text={t('settings.embeddingBackfill.start')}
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
              {batch
                ? t('settings.embeddingBackfill.progress', { done, total: batch.total_jobs })
                : t('settings.embeddingBackfill.starting')}
            </Typography>
            <IconButtonWithTooltip
              label={t('settings.embeddingBackfill.cancel')}
              onClick={cancel}
              icon={<CloseIcon />}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
};
