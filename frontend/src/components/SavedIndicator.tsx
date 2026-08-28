import type { SaveStatus } from '@/hooks/useSaveStatus.ts';
import { Box, Typography, type SxProps, type Theme } from '@mui/material';
import { AnimatePresence, motion } from 'motion/react';

const LABELS: Record<Exclude<SaveStatus, 'idle'>, string> = {
  saving: 'Saving...',
  saved: 'Saved',
};

interface SavedIndicatorProps {
  status: SaveStatus;
  sx?: SxProps<Theme>;
}

/**
 * The app's one marker for a save the reader never asked for: small, beside
 * the field that autosaved, gone again a moment later. Anything with an
 * explicit Save button reports itself through that button instead.
 *
 * The marker fades both ways. `AnimatePresence` holds the last text on screen
 * through the fade out — the status is already back to idle by then, so
 * rendering from it alone would blank the text before it had faded. One
 * constant key, so "Saving..." becoming "Saved" swaps the text in place rather
 * than fading the marker out and back in mid-save.
 */
export const SavedIndicator = ({ status, sx }: SavedIndicatorProps) => (
  <Box
    aria-live="polite"
    sx={[
      {
        // Reserved whether or not there is anything to say, so a save does not
        // shift the layout around the field.
        minHeight: '1.25rem',
      },
      ...(Array.isArray(sx) ? sx : [sx]),
    ]}
  >
    <AnimatePresence>
      {status !== 'idle' && (
        <motion.div
          key="saved-indicator"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: 'easeInOut' }}
        >
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {LABELS[status]}
          </Typography>
        </motion.div>
      )}
    </AnimatePresence>
  </Box>
);
