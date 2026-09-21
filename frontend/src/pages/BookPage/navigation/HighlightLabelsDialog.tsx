import { useGetBookHighlightLabels } from '@/api/generated/highlight-labels/highlight-labels.ts';
import type { HighlightLabelInBook } from '@/api/generated/model';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { ColorDot } from '@/components/highlights/ColorDot.tsx';
import { useHighlightLabelSave } from '@/components/highlights/useHighlightLabelSave.ts';
import { ColorSwatchPicker } from '@/components/inputs/ColorSwatchPicker.tsx';
import { SavedIndicator } from '@/components/SavedIndicator.tsx';
import { useSaveStatus } from '@/hooks/useSaveStatus.ts';
import { DEFAULT_LABEL_COLOR, LABEL_COLORS } from '@/utils/colorUtils.ts';
import { Box, Button, Divider, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

/** What the book calls a highlighter before the reader names it: `yellow / lighten`. */
const styleName = (label: HighlightLabelInBook): string => {
  const parts = [label.device_color, label.device_style].filter(Boolean);
  return parts.length > 0 ? parts.join(' / ') : 'Unlabelled';
};

const countOf = (count: number): string => (count === 1 ? '1 highlight' : `${count} highlights`);

interface LabelRowProps {
  bookId: number;
  label: HighlightLabelInBook;
}

/**
 * One highlighter of the book: what the reader calls it, and the colour it is
 * drawn in here.
 *
 * Both are the highlighter's, not any one highlight's, so the row leads with
 * how many highlights it speaks for. Autosaved like every other field in the
 * sidebar; a failure is reported by the snackbar and returns the marker to idle.
 */
const LabelRow = ({ bookId, label }: LabelRowProps) => {
  const [name, setName] = useState(label.label || '');
  const saveStatus = useSaveStatus();
  const edits = useHighlightLabelSave(bookId, saveStatus);

  const submitName = () => {
    if (edits.isSaving) return;
    const trimmed = name.trim();
    if (trimmed !== (label.label || '')) edits.save(label.id, { label: trimmed });
  };

  const changeColor = (ui_color: string) => {
    if (ui_color !== label.ui_color) edits.save(label.id, { ui_color });
  };

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
        <ColorDot color={label.ui_color || DEFAULT_LABEL_COLOR} />
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          {styleName(label)}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {countOf(label.highlight_count)}
        </Typography>
      </Stack>
      <TextField
        value={name}
        onChange={(event) => setName(event.target.value)}
        onBlur={submitName}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            submitName();
          }
        }}
        placeholder="Label name..."
        // Named per row: several of these fields sit in one dialog, and
        // "Label name..." alone would leave them indistinguishable.
        slotProps={{ htmlInput: { 'aria-label': `Name for ${styleName(label)}` } }}
        size="small"
        fullWidth
        sx={{ mb: 1.5 }}
      />
      <ColorSwatchPicker
        label={`Colour for ${styleName(label)}`}
        colors={LABEL_COLORS}
        value={label.ui_color}
        onChange={changeColor}
      />
      <SavedIndicator status={saveStatus.status} sx={{ mt: 1 }} />
    </Box>
  );
};

interface HighlightLabelsDialogProps {
  bookId: number;
  open: boolean;
  onClose: () => void;
}

/**
 * The book's highlighters, named and recoloured where it is plain what they
 * cover.
 *
 * This is the one place a label's display colour can be changed. It used to sit
 * in the dialog of a single highlight, under that highlight's own colour, where
 * it read as "make this one red" and instead repainted every highlight of the
 * colour in the book. Here each row says how many highlights it speaks for
 * before it offers anything to change.
 */
export const HighlightLabelsDialog = ({ bookId, open, onClose }: HighlightLabelsDialogProps) => {
  const { data } = useGetBookHighlightLabels(bookId, { query: { enabled: open } });
  const labels = data?.items ?? [];

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      title="Highlight labels"
      maxWidth="xs"
      footerActions={
        <Box sx={{ display: 'flex', width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose}>Done</Button>
        </Box>
      }
    >
      <Typography variant="body2" sx={{ color: 'text.secondary', pt: 2 }}>
        A label is the meaning of a highlighter, so its name and colour reach every highlight made
        with it in this book. To recolour one passage on its own, open it and pick a colour there.
      </Typography>
      <Stack divider={<Divider />} spacing={3} sx={{ mt: 3 }}>
        {labels.map((label) => (
          <LabelRow key={label.id} bookId={bookId} label={label} />
        ))}
      </Stack>
    </CommonDialog>
  );
};
