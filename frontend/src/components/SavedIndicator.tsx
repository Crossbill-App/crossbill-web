import type { SaveStatus } from '@/hooks/useSaveStatus.ts';
import { Typography, type SxProps, type Theme } from '@mui/material';

interface SavedIndicatorProps {
  status: SaveStatus;
  sx?: SxProps<Theme>;
}

/**
 * The app's one marker for a save the reader never asked for: small, beside
 * the field that autosaved, gone again a moment later. Anything with an
 * explicit Save button reports itself through that button instead.
 */
export const SavedIndicator = ({ status, sx }: SavedIndicatorProps) => (
  <Typography
    variant="caption"
    aria-live="polite"
    sx={[
      {
        color: 'text.secondary',
        // Reserved whether or not there is anything to say, so a save does not
        // shift the layout around the field.
        minHeight: '1.25rem',
        display: 'block',
        transition: 'opacity 0.2s ease',
        opacity: status === 'idle' ? 0 : 1,
      },
      ...(Array.isArray(sx) ? sx : [sx]),
    ]}
  >
    {status === 'saving' ? 'Saving...' : status === 'saved' ? 'Saved' : ''}
  </Typography>
);
