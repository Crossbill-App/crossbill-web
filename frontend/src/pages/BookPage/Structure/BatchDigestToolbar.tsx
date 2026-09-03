import { useEnqueueBookDigest, useGetActiveBookDigestBatch } from '@/api/generated/jobs/jobs';
import type { JobBatchResponse } from '@/api/generated/model';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { AIFeature } from '@/components/features/AIFeature';
import { useSnackbar } from '@/context/SnackbarContext';
import { useJobBatchProgress } from '@/hooks/useJobBatchProgress';
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
    showSnackbar('All chapter summaries are up to date.', 'success');
  } else if (batch.status === 'completed_with_errors') {
    showSnackbar(
      `Updated ${batch.completed_jobs}/${batch.total_jobs} summaries. Some chapters failed.`,
      'warning'
    );
  } else if (batch.status === 'failed') {
    showSnackbar('Summary update failed.', 'error');
  }
}

const summaryWord = (count: number) => (count === 1 ? 'summary' : 'summaries');

export const BatchDigestToolbar = ({
  bookId,
  eligibleChapterCount,
  existingSummaryCount,
}: BatchDigestToolbarProps) => {
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
      showSnackbar('Summary update cancelled. Completed changes were kept.', 'info');
    },
  });

  const { mutate: enqueue, isPending: isEnqueuing } = useEnqueueBookDigest({
    mutation: {
      onSuccess: (response) => {
        track(response.id);
      },
      onError: () => {
        showSnackbar('Failed to start summary update.', 'error');
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
            Updating summaries{total > 0 ? ` (${completed}/${total})` : '...'}
          </Typography>
          <IconButtonWithTooltip
            label="Cancel summary update"
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
      aria-label="Generate missing summaries"
      onClick={handleGenerateMissing}
      disabled={!canGenerateMissing}
      sx={{ minWidth: 40 }}
    >
      <AIIcon />
    </Button>
  );
  const moreActionsButton = (
    <Button
      aria-label="More summary actions"
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
      <ButtonGroup variant="text" size="small" aria-label="Summary generation actions">
        {canGenerateMissing ? (
          <Tooltip title="Generate missing summaries">{generateMissingButton}</Tooltip>
        ) : (
          generateMissingButton
        )}
        {canRegenerate ? (
          <Tooltip title="More summary actions">{moreActionsButton}</Tooltip>
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
          <ListItemText>Regenerate all summaries</ListItemText>
        </MenuItem>
      </Menu>

      <ConfirmationDialog
        open={confirmationOpen}
        onClose={() => setConfirmationOpen(false)}
        onConfirm={handleRegenerateAll}
        confirmText="Regenerate all"
        confirmColor="error"
        message={
          <Stack spacing={2}>
            <DialogContentText>
              This will replace {existingCount} existing {summaryWord(existingCount)} and generate{' '}
              {missingCount} missing {summaryWord(missingCount)}.
            </DialogContentText>
            <DialogContentText>
              The current summaries, key points, and questions will be replaced. Any saved answers
              to those questions will be deleted.
            </DialogContentText>
          </Stack>
        }
      />
    </AIFeature>
  );
};
