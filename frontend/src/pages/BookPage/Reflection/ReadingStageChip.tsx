import { useUpdateReadingStage } from '@/api/generated/books/books.ts';
import {
  READING_STAGE_LABELS,
  READING_STAGE_PROGRESSION,
  type ReadingStageValue,
} from '@/components/readingStage/readingStages.ts';
import { SavedIndicator } from '@/components/SavedIndicator.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useSaveStatus } from '@/hooks/useSaveStatus.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { Box, Chip, Divider, Menu, MenuItem } from '@mui/material';
import { useState } from 'react';

interface ReadingStageChipProps {
  bookId: number;
  readingStage: ReadingStageValue | null;
}

export const ReadingStageChip = ({ bookId, readingStage }: ReadingStageChipProps) => {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();

  const saveStatus = useSaveStatus();

  const { mutate: updateStage, isPending } = useUpdateReadingStage({
    mutation: {
      onSuccess: () => {
        saveStatus.saved();
        cache.bookChanged(bookId);
      },
      onError: (error: unknown) => {
        saveStatus.reset();
        mutationErrorHandler('update reading stage')(error);
      },
    },
  });

  const handleSelect = (stage: ReadingStageValue | null) => {
    setAnchorEl(null);
    if (stage === readingStage) return;
    saveStatus.saving();
    updateStage({ bookId, data: { reading_stage: stage } });
  };

  const abandoned = readingStage === 'did_not_finish';

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1.5 }}>
        <Chip
          label={readingStage ? READING_STAGE_LABELS[readingStage] : 'Set stage'}
          color={readingStage && !abandoned ? 'primary' : 'default'}
          variant={readingStage ? 'filled' : 'outlined'}
          onClick={(event) => setAnchorEl(event.currentTarget)}
          disabled={isPending}
        />
        <SavedIndicator status={saveStatus.status} sx={{ minHeight: 0 }} />
      </Box>
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
        {READING_STAGE_PROGRESSION.map((stage) => (
          <MenuItem
            key={stage}
            selected={stage === readingStage}
            onClick={() => handleSelect(stage)}
          >
            {READING_STAGE_LABELS[stage]}
          </MenuItem>
        ))}
        <Divider />
        <MenuItem selected={abandoned} onClick={() => handleSelect('did_not_finish')}>
          {READING_STAGE_LABELS.did_not_finish}
        </MenuItem>
        {readingStage && [
          <Divider key="clear-divider" />,
          <MenuItem key="clear" onClick={() => handleSelect(null)}>
            Clear stage
          </MenuItem>,
        ]}
      </Menu>
    </>
  );
};
