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
import { useTranslation } from 'react-i18next';
import { labelStyleName } from './labelStyleName.ts';

interface LabelRowProps {
  bookId: number;
  label: HighlightLabelInBook;
}

const LabelRow = ({ bookId, label }: LabelRowProps) => {
  const { t } = useTranslation();
  const [name, setName] = useState(label.label || '');
  const saveStatus = useSaveStatus();
  const edits = useHighlightLabelSave(bookId, saveStatus);

  const style = labelStyleName(label);

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
          {style}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {t('common.counts.highlights', { count: label.highlight_count })}
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
        placeholder={t('common.placeholders.labelName')}
        // Named per row: several of these fields sit in one dialog, and
        // "Label name..." alone would leave them indistinguishable.
        slotProps={{
          htmlInput: { 'aria-label': t('book.navigation.labelsDialog.nameFor', { style }) },
        }}
        size="small"
        fullWidth
        sx={{ mb: 1.5 }}
      />
      <ColorSwatchPicker
        label={t('book.navigation.labelsDialog.colourFor', { style })}
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
 */
export const HighlightLabelsDialog = ({ bookId, open, onClose }: HighlightLabelsDialogProps) => {
  const { t } = useTranslation();
  const { data } = useGetBookHighlightLabels(bookId, { query: { enabled: open } });
  const labels = data?.items ?? [];

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      title={t('book.navigation.labelsDialog.title')}
      maxWidth="xs"
      footerActions={
        <Box sx={{ display: 'flex', width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose}>{t('common.actions.done')}</Button>
        </Box>
      }
    >
      <Stack divider={<Divider />} spacing={3} sx={{ mt: 3 }}>
        {labels.map((label) => (
          <LabelRow key={label.id} bookId={bookId} label={label} />
        ))}
      </Stack>
    </CommonDialog>
  );
};
