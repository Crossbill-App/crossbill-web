import { Box, Tooltip } from '@mui/material';
import { readingStageMarker } from './readingStageMarker.ts';

export interface ReadingStageIconProps {
  stage: string | null | undefined;
}

/** The reading-stage marker for a book, or nothing when the stage has none. */
export const ReadingStageIcon = ({ stage }: ReadingStageIconProps) => {
  const marker = readingStageMarker(stage);
  if (!marker) return null;

  const { Icon, color, label } = marker;
  return (
    <Tooltip title={label}>
      <Box
        role="img"
        aria-label={label}
        sx={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          backgroundColor: `${color}.main`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: (theme) => `0 2px 8px ${theme.customColors.shadows.medium}`,
        }}
      >
        <Icon sx={{ fontSize: 16, color: `${color}.contrastText` }} />
      </Box>
    </Tooltip>
  );
};
