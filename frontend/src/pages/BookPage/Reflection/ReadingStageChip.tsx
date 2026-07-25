import { useUpdateReadingStage } from '@/api/generated/books/books.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { Chip, Menu, MenuItem } from '@mui/material';
import { useState } from 'react';
import { READING_STAGE_LABELS, READING_STAGES, type ReadingStageValue } from './readingStages';

interface ReadingStageChipProps {
  bookId: number;
  readingStage: ReadingStageValue | null;
}

export const ReadingStageChip = ({ bookId, readingStage }: ReadingStageChipProps) => {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();

  const { mutate: updateStage, isPending } = useUpdateReadingStage({
    mutation: {
      onSuccess: () => cache.bookChanged(bookId),
      onError: mutationErrorHandler('update reading stage'),
    },
  });

  const handleSelect = (stage: ReadingStageValue | null) => {
    setAnchorEl(null);
    if (stage === readingStage) return;
    updateStage({ bookId, data: { reading_stage: stage } });
  };

  return (
    <>
      <Chip
        label={readingStage ? READING_STAGE_LABELS[readingStage] : 'Set stage'}
        size="small"
        color={readingStage ? 'primary' : 'default'}
        variant={readingStage ? 'filled' : 'outlined'}
        onClick={(event) => setAnchorEl(event.currentTarget)}
        disabled={isPending}
        sx={{ mt: 1.5 }}
      />
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
        {READING_STAGES.map((stage) => (
          <MenuItem
            key={stage}
            selected={stage === readingStage}
            onClick={() => handleSelect(stage)}
          >
            {READING_STAGE_LABELS[stage]}
          </MenuItem>
        ))}
        {readingStage && <MenuItem onClick={() => handleSelect(null)}>Clear stage</MenuItem>}
      </Menu>
    </>
  );
};
