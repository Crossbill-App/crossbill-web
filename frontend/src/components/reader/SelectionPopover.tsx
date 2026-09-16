import type { EbookRect } from '@/components/reader/EbookReader.ts';
import { Button, Paper, Popper, Stack, useMediaQuery, useTheme } from '@mui/material';

export interface SelectionPopoverProps {
  /** Where the selected words sit on screen, `null` when nothing is selected. */
  rect: EbookRect | null;
  onHighlight: () => void;
  /** Carries the selection on to a word tapped later, over as many pages as it takes. */
  onExtend: () => void;
  onCancel: () => void;
}

/** Air between the words and these actions, enough that they read as belonging to them. */
const GAP_PX = 8;

// A phone draws its own Copy and Look Up against the selection -- about 44pt of menu
// and its arrow -- and offers no way to place it or ask where it went.
const PHONE_GAP_PX = 60;

type SelectionActionsProps = Omit<SelectionPopoverProps, 'rect'>;

const SelectionActions = ({ onHighlight, onExtend, onCancel }: SelectionActionsProps) => (
  // Never takes focus: away from the book's frame, the browser stops showing the selection.
  <Paper elevation={8} onMouseDown={(event) => event.preventDefault()} sx={{ p: 0.5 }}>
    <Stack role="toolbar" aria-label="Selected text" direction="row" spacing={0.5}>
      <Button onClick={onHighlight}>Highlight</Button>
      <Button onClick={onExtend}>Extend</Button>
      <Button onClick={onCancel}>Cancel</Button>
    </Stack>
  </Paper>
);

/** What can be done with the words selected in the book, below the rectangle they fill. */
export const SelectionPopover = ({ rect, ...actions }: SelectionPopoverProps) => {
  const theme = useTheme();
  const isPhone = useMediaQuery(theme.breakpoints.down('sm'));

  if (!rect) return null;

  // A Popper rather than a Popover: a backdrop would cover the book, and taking focus
  // out of its frame would drop the selection.
  return (
    <Popper
      open
      anchorEl={{ getBoundingClientRect: () => DOMRect.fromRect(rect) }}
      placement="bottom"
      modifiers={[{ name: 'offset', options: { offset: [0, isPhone ? PHONE_GAP_PX : GAP_PX] } }]}
      sx={{ zIndex: (t) => t.zIndex.appBar + 2 }}
    >
      <SelectionActions {...actions} />
    </Popper>
  );
};
