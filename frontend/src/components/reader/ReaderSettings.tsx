import { ChoiceSection } from '@/components/inputs/ChoiceSection.tsx';
import {
  READER_ALIGNMENT_LABELS,
  READER_ALIGNMENTS,
  READER_COLUMN_LABELS,
  READER_COLUMNS,
  READER_PAGE_COLOR_LABELS,
  READER_PAGE_COLORS,
  type ReaderPreferences,
} from '@/components/reader/readerPreferences.ts';
import { Popover, Stack } from '@mui/material';

interface ReaderSettingsProps {
  anchorEl: Element | null;
  onClose: () => void;
  preferences: ReaderPreferences;
  onChange: (preferences: ReaderPreferences) => void;
}

/** What the page looks like: its colour, how its lines are set, and in how many columns. */
export const ReaderSettings = ({
  anchorEl,
  onClose,
  preferences,
  onChange,
}: ReaderSettingsProps) => (
  <Popover
    open={anchorEl !== null}
    anchorEl={anchorEl}
    onClose={onClose}
    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
    // Readium suppresses a page turn while an interactive element has focus, and
    // `role=dialog` is what makes this paper — which holds it — count as one.
    slotProps={{
      paper: { role: 'dialog', 'aria-label': 'Appearance', sx: { p: 2.5, width: 320 } },
    }}
  >
    <Stack spacing={2}>
      <ChoiceSection
        heading="Page colour"
        options={READER_PAGE_COLORS}
        labels={READER_PAGE_COLOR_LABELS}
        value={preferences.pageColor}
        onSelect={(pageColor) => onChange({ ...preferences, pageColor })}
      />
      <ChoiceSection
        heading="Text alignment"
        options={READER_ALIGNMENTS}
        labels={READER_ALIGNMENT_LABELS}
        value={preferences.alignment}
        onSelect={(alignment) => onChange({ ...preferences, alignment })}
      />
      <ChoiceSection
        heading="Columns"
        options={READER_COLUMNS}
        labels={READER_COLUMN_LABELS}
        value={preferences.columns}
        onSelect={(columns) => onChange({ ...preferences, columns })}
      />
    </Stack>
  </Popover>
);
