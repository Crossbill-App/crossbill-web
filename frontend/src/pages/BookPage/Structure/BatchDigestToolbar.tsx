import { useEnqueueBookDigest, useGetActiveBookDigestBatch } from '@/api/generated/jobs/jobs';
import type { JobBatchResponse } from '@/api/generated/model';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { AIFeature } from '@/components/features/AIFeature';
import { useSnackbar } from '@/context/SnackbarContext';
import { useJobBatchProgress } from '@/hooks/useJobBatchProgress';
import { i18n } from '@/i18n';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { AIIcon, CloseIcon, DropdownIcon, RegenerateIcon } from '@/theme/Icons';
import {
  Box,
  Button,
  ButtonGroup,
  CircularProgress,
  DialogContentText,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { useCallback, useState, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

interface BatchDigestToolbarProps {
  bookId: number;
  eligibleChapterCount: number;
  existingSummaryCount?: number;
}

function showCompletionMessage(
  batch: JobBatchResponse,
  showSnackbar: (msg: string, severity: 'error' | 'warning' | 'info' | 'success') => void
) {
  if (batch.status === 'completed') {
    showSnackbar(i18n.t('structure.batchDigestToolbar.snackbar.completed'), 'success');
  } else if (batch.status === 'completed_with_errors') {
    showSnackbar(
      i18n.t('structure.batchDigestToolbar.snackbar.completedWithErrors', {
        completed: batch.completed_jobs,
        total: batch.total_jobs,
      }),
      'warning'
    );
  } else if (batch.status === 'failed') {
    showSnackbar(i18n.t('structure.batchDigestToolbar.snackbar.failed'), 'error');
  }
}

export const BatchDigestToolbar = ({
  bookId,
  eligibleChapterCount,
  existingSummaryCount,
}: BatchDigestToolbarProps) => {
  const { t } = useTranslation();
  const cache = useCacheEvents();
  const { showSnackbar } = useSnackbar();
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [confirmationOpen, setConfirmationOpen] = useState(false);

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
      showSnackbar(t('structure.batchDigestToolbar.snackbar.cancelled'), 'info');
    },
  });

  const { mutate: enqueue, isPending: isEnqueuing } = useEnqueueBookDigest({
    mutation: {
      onSuccess: (response) => {
        track(response.id);
      },
      onError: () => {
        showSnackbar(t('structure.batchDigestToolbar.snackbar.startFailed'), 'error');
      },
    },
  });

  const handleGenerateMissing = useCallback(() => {
    enqueue({ bookId });
  }, [enqueue, bookId]);

  const handleMenuOpen = (event: MouseEvent<HTMLButtonElement>) => {
    setMenuAnchor(event.currentTarget);
  };

  const handleRegenerateSelect = () => {
    setMenuAnchor(null);
    setConfirmationOpen(true);
  };

  const handleRegenerateAll = () => {
    setConfirmationOpen(false);
    enqueue({ bookId, params: { overwrite_existing: true } });
  };

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
            {total > 0
              ? t('structure.batchDigestToolbar.updatingProgress', { completed, total })
              : t('structure.batchDigestToolbar.updating')}
          </Typography>
          <IconButtonWithTooltip
            label={t('structure.batchDigestToolbar.cancelUpdate')}
            onClick={cancel}
            icon={<CloseIcon />}
          />
        </Box>
      </AIFeature>
    );
  }

  const countsLoaded = existingSummaryCount !== undefined;
  const existingCount = existingSummaryCount ?? 0;
  const missingCount = Math.max(eligibleChapterCount - existingCount, 0);
  const canGenerateMissing = eligibleChapterCount > 0 && (!countsLoaded || missingCount > 0);
  const canRegenerate = countsLoaded && existingCount > 0;
  const generateMissingButton = (
    <Button
      aria-label={t('structure.batchDigestToolbar.generateMissing')}
      onClick={handleGenerateMissing}
      disabled={!canGenerateMissing}
      sx={{ minWidth: 40 }}
    >
      <AIIcon />
    </Button>
  );
  const moreActionsButton = (
    <Button
      aria-label={t('structure.batchDigestToolbar.moreActions')}
      onClick={handleMenuOpen}
      disabled={!canRegenerate}
      aria-controls={menuAnchor ? 'summary-actions-menu' : undefined}
      aria-haspopup="menu"
      aria-expanded={menuAnchor ? 'true' : undefined}
      sx={{ minWidth: 32 }}
    >
      <DropdownIcon />
    </Button>
  );

  return (
    <AIFeature>
      <ButtonGroup
        variant="text"
        size="small"
        aria-label={t('structure.batchDigestToolbar.actionsLabel')}
      >
        {canGenerateMissing ? (
          <Tooltip title={t('structure.batchDigestToolbar.generateMissing')}>
            {generateMissingButton}
          </Tooltip>
        ) : (
          generateMissingButton
        )}
        {canRegenerate ? (
          <Tooltip title={t('structure.batchDigestToolbar.moreActions')}>
            {moreActionsButton}
          </Tooltip>
        ) : (
          moreActionsButton
        )}
      </ButtonGroup>

      <Menu
        id="summary-actions-menu"
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={() => setMenuAnchor(null)}
      >
        <MenuItem onClick={handleRegenerateSelect}>
          <ListItemIcon>
            <RegenerateIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t('structure.batchDigestToolbar.regenerateAll')}</ListItemText>
        </MenuItem>
      </Menu>

      <ConfirmationDialog
        open={confirmationOpen}
        onClose={() => setConfirmationOpen(false)}
        onConfirm={handleRegenerateAll}
        confirmText={t('structure.batchDigestToolbar.regenerateConfirm.confirm')}
        confirmColor="error"
        message={
          <Stack spacing={2}>
            <DialogContentText>
              {t('structure.batchDigestToolbar.regenerateConfirm.message', {
                existing: t('structure.batchDigestToolbar.regenerateConfirm.existingSummaries', {
                  count: existingCount,
                }),
                missing: t('structure.batchDigestToolbar.regenerateConfirm.missingSummaries', {
                  count: missingCount,
                }),
              })}
            </DialogContentText>
            <DialogContentText>
              {t('structure.batchDigestToolbar.regenerateConfirm.warning')}
            </DialogContentText>
          </Stack>
        }
      />
    </AIFeature>
  );
};
