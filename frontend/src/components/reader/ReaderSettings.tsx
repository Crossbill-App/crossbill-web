import { chromeMarkerProps } from '@/components/reader/chromeMarker.ts';
import {
  READER_THEMES,
  READER_THEME_LABELS,
  type ReaderPreferences,
  type ReaderThemeName,
} from '@/components/reader/readerPreferences.ts';
import {
  Box,
  Popover,
  Slider,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';

interface ReaderSettingsProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  preferences: ReaderPreferences;
  onChange: (preferences: ReaderPreferences) => void;
  /** The range and step the navigator's own `EpubPreferencesEditor` reports for font size. */
  fontSizeRange: [number, number];
  fontSizeStep: number;
}

const asPercentage = (multiplier: number) => `${Math.round(multiplier * 100)}%`;

/**
 * The reader's appearance controls: how big the text is, and what colour the
 * page is.
 *
 * Deliberately two settings. Readium exposes forty, and the ones worth having
 * in a first reader are the two every e-reader opens with; the rest can be
 * added once there is a reason to prefer one over the book's own typography.
 */
export const ReaderSettings = ({
  anchorEl,
  onClose,
  preferences,
  onChange,
  fontSizeRange,
  fontSizeStep,
}: ReaderSettingsProps) => (
  <Popover
    open={anchorEl !== null}
    anchorEl={anchorEl}
    onClose={onClose}
    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
    slotProps={{ paper: { sx: { p: 2.5, width: 280 } } }}
  >
    <Stack spacing={3} {...chromeMarkerProps}>
      <Box>
        <Typography variant="h6" component="h2" gutterBottom>
          Font size
        </Typography>
        <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
          <Slider
            aria-label="Font size"
            value={preferences.fontSize}
            min={fontSizeRange[0]}
            max={fontSizeRange[1]}
            step={fontSizeStep}
            onChange={(_event, value) => onChange({ ...preferences, fontSize: value })}
            valueLabelDisplay="off"
          />
          <Typography variant="body2" sx={{ minWidth: 48, textAlign: 'right' }}>
            {asPercentage(preferences.fontSize)}
          </Typography>
        </Stack>
      </Box>

      <Box>
        <Typography variant="h6" component="h2" gutterBottom>
          Page colour
        </Typography>
        <ToggleButtonGroup
          exclusive
          fullWidth
          size="small"
          value={preferences.theme}
          aria-label="Page colour"
          onChange={(_event, value: ReaderThemeName | null) => {
            // Null when the pressed button was already the active one; a
            // reading theme is never "none", so that click means nothing.
            if (value !== null) onChange({ ...preferences, theme: value });
          }}
        >
          {READER_THEMES.map((name) => (
            <ToggleButton key={name} value={name}>
              {READER_THEME_LABELS[name]}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>
    </Stack>
  </Popover>
);
