import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import type { readerPageColors } from '@/components/reader/readerPreferences.ts';
import { ChapterListIcon, CloseIcon, PaletteIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { alpha, Box, Stack, Toolbar, Typography } from '@mui/material';

export interface ReaderToolbarProps {
  title: string;
  /** Where in the book the reader is, `undefined` until the engine has said. */
  page: number | undefined;
  pageCount: number;
  progression: number | undefined;
  /** The contents and appearance of a book that is not open yet are nothing to offer. */
  isOpen: boolean;
  colors: ReturnType<typeof readerPageColors>;
  onOpenContents: () => void;
  onOpenAppearance: (anchor: Element) => void;
  onClose: () => void;
}

const pageLabel = (page: number, pageCount: number, progression: number | undefined) =>
  `Page ${page} of ${pageCount}` +
  (progression === undefined ? '' : ` · ${Math.round(progression * 100)}%`);

/** The reader's title bar: what is being read, where in it, and the ways out of the page. */
export const ReaderToolbar = ({
  title,
  page,
  pageCount,
  progression,
  isOpen,
  colors,
  onOpenContents,
  onOpenAppearance,
  onClose,
}: ReaderToolbarProps) => (
  <Box sx={{ borderBottom: 1, borderColor: alpha(colors.text, 0.12) }}>
    <Toolbar variant="dense" sx={{ gap: 1 }}>
      <IconButtonWithTooltip
        label="Contents"
        onClick={onOpenContents}
        disabled={!isOpen}
        edge="start"
        icon={<ChapterListIcon sx={{ fontSize: ICON_SIZE.ui }} />}
      />
      <Stack sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="h6" component="h1" noWrap>
          {title}
        </Typography>
        {pageCount > 0 && page !== undefined && (
          // 0.7 of the page's own text, which is 6.3:1 on the light page
          // and 8.4:1 on the dark one; body text needs 4.5:1.
          <Typography variant="body2" noWrap sx={{ color: alpha(colors.text, 0.7) }}>
            {pageLabel(page, pageCount, progression)}
          </Typography>
        )}
      </Stack>
      <IconButtonWithTooltip
        label="Appearance"
        onClick={(event) => onOpenAppearance(event.currentTarget)}
        disabled={!isOpen}
        icon={<PaletteIcon sx={{ fontSize: ICON_SIZE.ui }} />}
      />
      <IconButtonWithTooltip
        label="Close reader"
        onClick={onClose}
        edge="end"
        icon={<CloseIcon sx={{ fontSize: ICON_SIZE.ui }} />}
      />
    </Toolbar>
  </Box>
);
