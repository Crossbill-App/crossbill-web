import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, Tooltip } from '@mui/material';
import { readingStageMarker } from './readingStageMarker.ts';

export interface ReadingStageIconProps {
  stage: string | null | undefined;
}

/** The reading-stage marker for a book, or nothing when the stage has none. */
export const ReadingStageIcon = ({ stage }: ReadingStageIconProps) => {
  const marker = readingStageMarker(stage);
  if (!marker) return null;

  const { Icon, label } = marker;
  return (
    <Tooltip title={label}>
      <Box
        role="img"
        aria-label={label}
        sx={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          backgroundColor: 'primary.main',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: (theme) => `0 2px 8px ${theme.customColors.shadows.medium}`,
        }}
      >
        <Icon sx={{ fontSize: ICON_SIZE.inline, color: 'primary.contrastText' }} />
      </Box>
    </Tooltip>
  );
};
