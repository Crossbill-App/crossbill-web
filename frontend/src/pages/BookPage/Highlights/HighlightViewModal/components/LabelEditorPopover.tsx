import { useUpdateHighlightLabel } from '@/api/generated/highlight-labels/highlight-labels.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { LABEL_COLORS } from '@/utils/colorUtils.ts';
import { Box, Popover, TextField, Typography } from '@mui/material';
import { type MutableRefObject, useEffect, useRef, useState } from 'react';
import { CirclePicker, type ColorResult } from 'react-color';

interface LabelEditorContentProps {
  styleId: number;
  currentLabel?: string | null;
  currentColor?: string | null;
  bookId: number;
  submitRef: MutableRefObject<(() => void) | null>;
  onClose: () => void;
}

/**
 * Inner content component that remounts each time the popover opens,
 * ensuring labelText state resets from currentLabel prop.
 * Exposes handleLabelSubmit via submitRef so the outer Popover can
 * trigger a submit on close (before the content unmounts).
 */
const LabelEditorContent = ({
  styleId,
  currentLabel,
  currentColor,
  bookId,
  submitRef,
  onClose,
}: LabelEditorContentProps) => {
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const [labelText, setLabelText] = useState(currentLabel || '');

  const updateMutation = useUpdateHighlightLabel({
    mutation: {
      onSuccess: () => {
        cache.highlightLabelsChanged(bookId);
      },
      onError: mutationErrorHandler('update label'),
    },
  });

  const handleLabelSubmit = () => {
    if (updateMutation.isPending) return;
    const trimmed = labelText.trim();
    if (trimmed !== (currentLabel || '')) {
      updateMutation.mutate({
        styleId,
        data: { label: trimmed },
      });
    }
  };

  // Expose submit to the outer Popover so it can call it before closing
  useEffect(() => {
    submitRef.current = handleLabelSubmit;
  });

  const handleColorChange = (color: ColorResult) => {
    updateMutation.mutate({
      styleId,
      data: { ui_color: color.hex },
    });
  };

  return (
    <Box sx={{ p: 2, width: 280 }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
        Edit Label
      </Typography>
      <TextField
        value={labelText}
        onChange={(e) => setLabelText(e.target.value)}
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
        autoFocus
        sx={{ mb: 2 }}
      />
      <Typography variant="caption" sx={{ mb: 1, display: 'block', color: 'text.secondary' }}>
        Color
      </Typography>
      <CirclePicker
        color={currentColor || undefined}
        colors={LABEL_COLORS}
        onChangeComplete={handleColorChange}
        width="100%"
      />
    </Box>
  );
};

interface LabelEditorPopoverProps {
  anchorEl: HTMLElement | null;
  open: boolean;
  onClose: () => void;
  styleId: number;
  currentLabel?: string | null;
  currentColor?: string | null;
  bookId: number;
}

export const LabelEditorPopover = ({
  anchorEl,
  open,
  onClose,
  styleId,
  currentLabel,
  currentColor,
  bookId,
}: LabelEditorPopoverProps) => {
  const submitRef = useRef<(() => void) | null>(null);

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
        <LabelEditorContent
          styleId={styleId}
          currentLabel={currentLabel}
          currentColor={currentColor}
          bookId={bookId}
          submitRef={submitRef}
          onClose={onClose}
        />
      )}
    </Popover>
  );
};
