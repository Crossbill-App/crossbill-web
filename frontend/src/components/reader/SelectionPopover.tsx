import type { EbookSelection } from '@/components/reader/EbookReader.ts';
import { Button, Paper, Popper, Stack } from '@mui/material';

export interface SelectionPopoverProps {
  selection: EbookSelection | null;
  onHighlight: () => void;
  onCancel: () => void;
}

/** What can be done with the words selected in the book, below them. */
export const SelectionPopover = ({ selection, onHighlight, onCancel }: SelectionPopoverProps) => {
  const rect = selection?.rect;
  const anchor = rect && { getBoundingClientRect: () => DOMRect.fromRect(rect) };

  // A Popper rather than a Popover: a backdrop would cover the book, and taking focus
  // out of its frame would drop the selection. Below, clear of a phone's own callout.
  return (
    <Popper
      open={anchor !== undefined}
      anchorEl={anchor}
      placement="bottom"
      sx={{ zIndex: (theme) => theme.zIndex.appBar + 2 }}
    >
      <Paper elevation={8} onMouseDown={(event) => event.preventDefault()} sx={{ mt: 1, p: 0.5 }}>
        <Stack role="toolbar" aria-label="Selected text" direction="row" spacing={0.5}>
          <Button onClick={onHighlight}>Highlight</Button>
          <Button onClick={onCancel}>Cancel</Button>
        </Stack>
      </Paper>
    </Popper>
  );
};
