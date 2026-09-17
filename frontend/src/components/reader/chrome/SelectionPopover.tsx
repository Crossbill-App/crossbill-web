import { ColorDot } from '@/components/highlights/ColorDot.tsx';
import type { EbookRect } from '@/components/reader/engine/EbookReader.ts';
import type { HighlightColor } from '@/components/reader/highlights/highlightPalette.ts';
import {
  Box,
  Button,
  MenuItem,
  Paper,
  Popper,
  Select,
  Stack,
  useMediaQuery,
  useTheme,
  type SelectProps,
} from '@mui/material';
import { useState } from 'react';

export interface SelectionPopoverProps {
  /** Where the selected words sit on screen, `null` when nothing is selected. */
  rect: EbookRect | null;
  /** The colours a highlight can be made in. */
  palette: HighlightColor[];
  /** The colour Highlight will use. */
  selected: HighlightColor;
  /** Marks a colour as the one to highlight in, storing nothing. */
  onSelect: (color: HighlightColor) => void;
  /** Lets go of the selection and stores the passage in the selected colour. */
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

// Wide enough for the nine colours' own names; a book's own label for one can be
// any length, and past this it is the name that gives way rather than the row,
// which on a phone has no room to spare.
const COLOR_WIDTH_PX = 140;

const keepFocus = (event: { preventDefault: () => void }) => event.preventDefault();

// Open, the menu leaves focus where it found it too: `autoFocus: false` keeps the
// list from moving focus into itself, `disableAutoFocus: true` the modal under it.
const MENU_LEAVES_FOCUS_ALONE: SelectProps['MenuProps'] = {
  autoFocus: false,
  disableAutoFocus: true,
  // For a real browser rather than the tests: there, pressing an option focuses
  // it, and focus off the book's frame is the selection gone.
  slotProps: { paper: { onMouseDown: keepFocus } },
};

/** One colour as the dropdown says it: its hue, then the name the book gives it. */
const ColorChoice = ({ color }: { color: HighlightColor }) => (
  <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', minWidth: 0 }}>
    <ColorDot color={color.tint} />
    <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
      {color.name}
    </Box>
  </Stack>
);

type SelectionActionsProps = Omit<SelectionPopoverProps, 'rect'>;

const SelectionActions = ({
  palette,
  selected,
  onSelect,
  onHighlight,
  onExtend,
  onCancel,
}: SelectionActionsProps) => {
  // Held here because the dropdown is opened from a mousedown of our own; the
  // Select's own one focuses the dropdown before opening it.
  const [isChoosingColor, setIsChoosingColor] = useState(false);
  // Once the reader has tabbed to the dropdown, focus has already left the book's
  // frame: there is no selection left to protect, so the menu may take focus as usual.
  const [openedByPointer, setOpenedByPointer] = useState(false);

  return (
    // Never takes focus: away from the book's frame, the browser stops showing the selection.
    <Paper elevation={8} onMouseDown={keepFocus} sx={{ maxWidth: 'calc(100vw - 16px)', p: 0.5 }}>
      <Stack role="toolbar" aria-label="Selected text" direction="row" spacing={0.5}>
        <Select
          size="small"
          sx={{ maxWidth: COLOR_WIDTH_PX, minWidth: 0 }}
          value={selected.device_color}
          // MUI puts this on the display element, which is what carries the
          // combobox role; `slotProps.htmlInput` would label the hidden input.
          inputProps={{ 'aria-label': 'Highlight colour' }}
          MenuProps={openedByPointer ? MENU_LEAVES_FOCUS_ALONE : undefined}
          open={isChoosingColor}
          // Only the keyboard arrives here: the mousedown below opens the menu itself.
          onOpen={() => {
            setOpenedByPointer(false);
            setIsChoosingColor(true);
          }}
          onClose={() => setIsChoosingColor(false)}
          SelectDisplayProps={{
            onMouseDown: (event) => {
              keepFocus(event);
              setOpenedByPointer(true);
              setIsChoosingColor(true);
            },
          }}
        >
          {palette.map((color) => (
            <MenuItem
              key={color.device_color}
              value={color.device_color}
              onClick={() => onSelect(color)}
            >
              <ColorChoice color={color} />
            </MenuItem>
          ))}
        </Select>
        <Button size="small" onClick={onHighlight}>
          Highlight
        </Button>
        <Button size="small" onClick={onExtend}>
          Extend
        </Button>
        <Button size="small" onClick={onCancel}>
          Cancel
        </Button>
      </Stack>
    </Paper>
  );
};

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
