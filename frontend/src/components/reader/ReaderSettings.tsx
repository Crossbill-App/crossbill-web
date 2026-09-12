import { ChoiceSection } from '@/components/inputs/ChoiceSection.tsx';
import {
  READER_ALIGNMENT_LABELS,
  READER_ALIGNMENTS,
  READER_COLUMN_LABELS,
  READER_COLUMNS,
  READER_LINE_HEIGHT_LABELS,
  READER_LINE_HEIGHTS,
  READER_PAGE_COLOR_LABELS,
  READER_PAGE_COLORS,
  type ReaderPreferences,
} from '@/components/reader/readerPreferences.ts';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { LargerTextIcon, SmallerTextIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, IconButton, InputAdornment, Popover, Stack, TextField } from '@mui/material';
import { useState } from 'react';

const FONT_SIZE_STEP = 0.25;

const asPercent = (fontSize: number) => String(Math.round(fontSize * 100));

// A size clamped to the range, or typed, need not sit on a step. Carrying that
// offset forward would put the size the book opened at out of the buttons' reach.
const steppedFrom = (fontSize: number, direction: 1 | -1) => {
  const steps = fontSize / FONT_SIZE_STEP;
  return (direction === 1 ? Math.floor(steps) + 1 : Math.ceil(steps) - 1) * FONT_SIZE_STEP;
};

const clamped = (fontSize: number, [min, max]: [number, number]) =>
  Math.min(Math.max(fontSize, min), max);

interface FontSizeSectionProps {
  range: [number, number];
  value: number;
  onChange: (fontSize: number) => void;
}

const FontSizeSection = ({ range, value, onChange }: FontSizeSectionProps) => {
  const [typed, setTyped] = useState(asPercent(value));
  const apply = (fontSize: number) => {
    setTyped(asPercent(fontSize));
    // Enter and then a blur commit the same size twice, and the engine reflows
    // the book on every appearance it is handed.
    if (asPercent(fontSize) !== asPercent(value)) onChange(fontSize);
  };
  // On blur and Enter rather than per keystroke: "1" on the way to "150" is a
  // size of its own, and each one would reach the engine.
  const commit = () => {
    const percent = Number(typed);
    if (typed.trim() === '' || !Number.isFinite(percent)) {
      setTyped(asPercent(value));
      return;
    }
    apply(clamped(Math.round(percent) / 100, range));
  };

  const step = (direction: 1 | -1) => apply(clamped(steppedFrom(value, direction), range));

  return (
    <Box>
      <SectionTitle>Font size</SectionTitle>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        <IconButton aria-label="Smaller text" disabled={value <= range[0]} onClick={() => step(-1)}>
          <SmallerTextIcon sx={{ fontSize: ICON_SIZE.ui }} />
        </IconButton>
        <TextField
          size="small"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          onBlur={commit}
          // The arrows a reader reaches for in a number field. They cannot turn
          // the page: Readium suppresses its page turns while an input has focus.
          onKeyDown={(event) => {
            if (event.key === 'Enter') commit();
            if (event.key === 'ArrowUp') step(1);
            if (event.key === 'ArrowDown') step(-1);
          }}
          slotProps={{
            htmlInput: { 'aria-label': 'Font size in percent', inputMode: 'numeric' },
            input: { endAdornment: <InputAdornment position="end">%</InputAdornment> },
          }}
          sx={{ flex: 1 }}
        />
        <IconButton aria-label="Larger text" disabled={value >= range[1]} onClick={() => step(1)}>
          <LargerTextIcon sx={{ fontSize: ICON_SIZE.ui }} />
        </IconButton>
      </Stack>
    </Box>
  );
};

interface ReaderSettingsProps {
  anchorEl: Element | null;
  onClose: () => void;
  preferences: ReaderPreferences;
  onChange: (preferences: ReaderPreferences) => void;
  fontSizeRange: [number, number];
}

/** What the page looks like: text size, colour, how the lines are set, and in how many columns. */
export const ReaderSettings = ({
  anchorEl,
  onClose,
  preferences,
  onChange,
  fontSizeRange,
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
      <FontSizeSection
        range={fontSizeRange}
        value={preferences.fontSize}
        onChange={(fontSize) => onChange({ ...preferences, fontSize })}
      />
      <ChoiceSection
        heading="Line height"
        options={READER_LINE_HEIGHTS}
        labels={READER_LINE_HEIGHT_LABELS}
        value={preferences.lineHeight}
        onSelect={(lineHeight) => onChange({ ...preferences, lineHeight })}
      />
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
