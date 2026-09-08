import { chromeMarkerProps } from '@/components/reader/chromeMarker.ts';
import {
  READER_ALIGNMENT_LABELS,
  READER_ALIGNMENTS,
  READER_THEME_LABELS,
  READER_THEMES,
  type ReaderPreferences,
} from '@/components/reader/readerPreferences.ts';
import {
  Box,
  FormControlLabel,
  Popover,
  Slider,
  Stack,
  Switch,
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
  /**
   * Whether the viewport is wide enough for a second column to be possible.
   * Where it is not, the column control would be a switch that changed
   * nothing, so it is not offered at all.
   */
  canChooseColumns: boolean;
}

const asPercentage = (multiplier: number) => `${Math.round(multiplier * 100)}%`;

interface ChoiceSectionProps<Option extends string> {
  /** The heading above the control, and the group's accessible name. */
  heading: string;
  options: readonly Option[];
  labels: Record<Option, string>;
  value: Option;
  onSelect: (option: Option) => void;
}

/** A headed row of mutually exclusive choices — the popover's shape for a setting. */
const ChoiceSection = <Option extends string>({
  heading,
  options,
  labels,
  value,
  onSelect,
}: ChoiceSectionProps<Option>) => (
  <Box>
    <Typography variant="h6" component="h2" gutterBottom>
      {heading}
    </Typography>
    <ToggleButtonGroup
      exclusive
      fullWidth
      size="small"
      value={value}
      aria-label={heading}
      onChange={(_event, chosen: Option | null) => {
        // Null when the pressed button was already the active one. Every one of
        // these settings always has a value, so that click means nothing.
        if (chosen !== null) onSelect(chosen);
      }}
    >
      {options.map((option) => (
        <ToggleButton key={option} value={option}>
          {labels[option]}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  </Box>
);

/**
 * The reader's appearance controls: how big the text is, what colour the page
 * is, how the lines are set, and how many columns they are set in.
 *
 * Deliberately four settings. Readium exposes forty, and these are the ones a
 * reader reaches for daily; the rest can be added once there is a reason to
 * prefer one over the book's own typography. Two of them — alignment and
 * columns — open on "whatever the book and the screen already decided", so
 * that opening this popover and closing it again changes nothing.
 */
export const ReaderSettings = ({
  anchorEl,
  onClose,
  preferences,
  onChange,
  fontSizeRange,
  fontSizeStep,
  canChooseColumns,
}: ReaderSettingsProps) => (
  <Popover
    open={anchorEl !== null}
    anchorEl={anchorEl}
    onClose={onClose}
    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
    slotProps={{ paper: { sx: { p: 2.5, width: 320 } } }}
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

      <ChoiceSection
        heading="Page colour"
        options={READER_THEMES}
        labels={READER_THEME_LABELS}
        value={preferences.theme}
        onSelect={(theme) => onChange({ ...preferences, theme })}
      />

      <ChoiceSection
        heading="Text alignment"
        options={READER_ALIGNMENTS}
        labels={READER_ALIGNMENT_LABELS}
        value={preferences.alignment}
        onSelect={(alignment) => onChange({ ...preferences, alignment })}
      />

      {canChooseColumns && (
        <FormControlLabel
          control={
            <Switch
              checked={preferences.singleColumn}
              onChange={(event) => onChange({ ...preferences, singleColumn: event.target.checked })}
            />
          }
          label="Single column"
        />
      )}
    </Stack>
  </Popover>
);
