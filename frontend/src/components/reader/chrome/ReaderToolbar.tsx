import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { readerControlSx } from '@/components/reader/chrome/readerOverlay.ts';
import type { readerPageColors } from '@/components/reader/preferences/readerPreferences.ts';
import { ChapterListIcon, CloseIcon, PaletteIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { alpha, Box, Toolbar, Typography } from '@mui/material';

export interface ReaderToolbarProps {
  title: string;
  /** The contents and appearance of a book that is not open yet are nothing to offer. */
  isOpen: boolean;
  colors: ReturnType<typeof readerPageColors>;
  onOpenContents: () => void;
  onOpenAppearance: (anchor: Element) => void;
  onClose: () => void;
}

/**
 * The reader's title bar: what is being read and the ways out of the page.
 *
 * It sits on the book's page rather than on any surface of the app's, so the
 * page colour has to decide everything in it. The title followed it from the
 * start; the buttons did not, and kept `IconButton`'s default black glyph on
 * the dark page.
 */
export const ReaderToolbar = ({
  title,
  isOpen,
  colors,
  onOpenContents,
  onOpenAppearance,
  onClose,
}: ReaderToolbarProps) => {
  const controlSx = readerControlSx(colors);

  return (
    <Box sx={{ borderBottom: 1, borderColor: alpha(colors.text, 0.12) }}>
      <Toolbar variant="dense">
        <IconButtonWithTooltip
          label="Contents"
          onClick={onOpenContents}
          disabled={!isOpen}
          edge="start"
          color="inherit"
          sx={controlSx}
          icon={<ChapterListIcon sx={{ fontSize: ICON_SIZE.ui }} />}
        />
        <Typography variant="h6" component="h1" noWrap sx={{ flex: 1, minWidth: 0 }}>
          {title}
        </Typography>
        <IconButtonWithTooltip
          label="Appearance"
          onClick={(event) => onOpenAppearance(event.currentTarget)}
          disabled={!isOpen}
          color="inherit"
          sx={controlSx}
          icon={<PaletteIcon sx={{ fontSize: ICON_SIZE.ui }} />}
        />
        <IconButtonWithTooltip
          label="Close reader"
          onClick={onClose}
          edge="end"
          color="inherit"
          sx={controlSx}
          icon={<CloseIcon sx={{ fontSize: ICON_SIZE.ui }} />}
        />
      </Toolbar>
    </Box>
  );
};
