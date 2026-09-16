import type { readerPageColors } from '@/components/reader/readerPreferences.ts';
import { alpha, Button, Stack, Typography } from '@mui/material';

export interface ExtensionBarProps {
  colors: ReturnType<typeof readerPageColors>;
  onCancel: () => void;
}

/** What to do while the far end of a passage is awaited, in the page's own colours. */
export const ExtensionBar = ({ colors, onCancel }: ExtensionBarProps) => (
  <Stack
    role="group"
    aria-label="Extending the highlight"
    direction="row"
    spacing={1}
    sx={{
      alignItems: 'center',
      px: 1.5,
      py: 0.5,
      borderRadius: 1,
      border: 1,
      borderColor: alpha(colors.text, 0.12),
      boxShadow: (t) => t.shadows[2],
      backgroundColor: colors.background,
      color: colors.text,
    }}
  >
    <Typography variant="body2">Tap where the highlight ends</Typography>
    <Button size="small" color="inherit" onClick={onCancel}>
      Cancel
    </Button>
  </Stack>
);
