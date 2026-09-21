import { useGetBookHighlightLabels } from '@/api/generated/highlight-labels/highlight-labels.ts';
import { useChangeHighlightColor } from '@/api/generated/highlights/highlights.ts';
import type { HighlightLabelInBook } from '@/api/generated/model';
import { useHighlightLabelSave } from '@/components/highlights/useHighlightLabelSave.ts';
import { ColorSwatchPicker } from '@/components/inputs/ColorSwatchPicker.tsx';
import { SavedIndicator } from '@/components/SavedIndicator.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { useSaveStatus } from '@/hooks/useSaveStatus.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { LABEL_COLORS, type ColorOption } from '@/utils/colorUtils.ts';
import { Box, Divider, Popover, TextField, Typography } from '@mui/material';
import { useEffect, useRef, useState, type MutableRefObject } from 'react';

/** The nine colours KOReader draws with, the ones a highlight can be marked in. */
const DEVICE_COLOR_OPTIONS: readonly ColorOption[] = LABEL_COLORS.filter(
  (option) => option.device_color
);

/** What a KOReader colour is called before the book gives it a name of its own. */
const deviceColorName = (device_color: string | null | undefined): string =>
  DEVICE_COLOR_OPTIONS.find((option) => option.device_color === device_color)?.name ??
  device_color ??
  'this colour';

/** The swatch standing for a KOReader colour, which is how the picker marks it chosen. */
const deviceColorSwatch = (device_color: string | null | undefined): string | null =>
  DEVICE_COLOR_OPTIONS.find((option) => option.device_color === device_color)?.value ?? null;

interface HighlightStyleContentProps {
  bookId: number;
  highlightId: number;
  /** The style the highlight is filed under: its colour, and the label naming that colour. */
  style: HighlightLabelInBook | undefined;
  styleId: number;
  currentLabel?: string | null;
  submitRef: MutableRefObject<(() => void) | null>;
  onClose: () => void;
}

const HighlightStyleContent = ({
  bookId,
  highlightId,
  style,
  styleId,
  currentLabel,
  submitRef,
  onClose,
}: HighlightStyleContentProps) => {
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const [labelText, setLabelText] = useState(currentLabel || '');
  const saveStatus = useSaveStatus();

  // The field follows the colour the highlight has just been moved to, whose
  // label is another one's. Reset rather than remounted: a popover rebuilt under
  // the reader mid-edit reads as a second one opening on top of the first.
  useResetOnChange([styleId], () => setLabelText(currentLabel || ''));

  const labelSave = useHighlightLabelSave(bookId, saveStatus);

  const colorMutation = useChangeHighlightColor({
    mutation: {
      onSuccess: () => {
        saveStatus.saved();
        cache.highlightColorChanged(bookId);
      },
      onError: (error: unknown) => {
        saveStatus.reset();
        mutationErrorHandler('change the highlight colour')(error);
      },
    },
  });

  const handleLabelSubmit = () => {
    if (labelSave.isSaving) return;
    const trimmed = labelText.trim();
    if (trimmed !== (currentLabel || '')) labelSave.save(styleId, { label: trimmed });
  };

  // Expose submit to the outer Popover so it can call it before closing
  useEffect(() => {
    submitRef.current = handleLabelSubmit;
  });

  const handleDeviceColorChange = (swatch: string) => {
    const chosen = DEVICE_COLOR_OPTIONS.find((option) => option.value === swatch)?.device_color;
    if (!chosen || chosen === style?.device_color) return;
    saveStatus.saving();
    colorMutation.mutate({
      bookId,
      highlightId,
      // The drawer stays as it is: the reader picked a colour, not a pen.
      data: { device_color: chosen, device_style: style?.device_style ?? undefined },
    });
  };

  const colorName = deviceColorName(style?.device_color);

  return (
    <Box sx={{ p: 2, width: 300 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
        Highlight label
      </Typography>
      <ColorSwatchPicker
        label="Highlight colour"
        colors={DEVICE_COLOR_OPTIONS}
        value={deviceColorSwatch(style?.device_color)}
        onChange={handleDeviceColorChange}
      />

      <Divider sx={{ my: 2 }} />

      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
        {`Label for ${colorName}`}
      </Typography>
      <TextField
        value={labelText}
        onChange={(e) => setLabelText(e.target.value)}
        onBlur={handleLabelSubmit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            handleLabelSubmit();
            onClose();
          }
        }}
        placeholder="Label name..."
        size="small"
        fullWidth
      />
      <SavedIndicator status={saveStatus.status} />
    </Box>
  );
};

interface HighlightStylePopoverProps {
  anchorEl: HTMLElement | null;
  open: boolean;
  onClose: () => void;
  bookId: number;
  highlightId: number;
  styleId: number;
  currentLabel?: string | null;
}

/** What a highlight is drawn with: its own colour, and the name of that colour. */
export const HighlightStylePopover = ({
  anchorEl,
  open,
  onClose,
  bookId,
  highlightId,
  styleId,
  currentLabel,
}: HighlightStylePopoverProps) => {
  const submitRef = useRef<(() => void) | null>(null);
  const { data } = useGetBookHighlightLabels(bookId, { query: { enabled: open } });
  const style = data?.items.find((candidate) => candidate.id === styleId);

  const handleClose = () => {
    submitRef.current?.();
    onClose();
  };

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={handleClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
    >
      {open && (
        <HighlightStyleContent
          bookId={bookId}
          highlightId={highlightId}
          style={style}
          styleId={styleId}
          currentLabel={currentLabel}
          submitRef={submitRef}
          onClose={onClose}
        />
      )}
    </Popover>
  );
};
