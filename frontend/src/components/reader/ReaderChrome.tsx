import { chromeMarkerProps } from '@/components/reader/chromeMarker.ts';
import type { ReaderPreferences } from '@/components/reader/readerPreferences.ts';
import { ReaderSettings } from '@/components/reader/ReaderSettings.tsx';
import { ChapterListIcon, CloseIcon, PaletteIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, IconButton, Stack, Toolbar, Tooltip, Typography } from '@mui/material';
import { useState } from 'react';

interface ReaderChromeProps {
  title: string;
  /** "Page 12 of 340 · 4%", or nothing when the book publishes no position list. */
  positionLabel: string | null;
  onOpenToc: () => void;
  onClose: () => void;
  preferences: ReaderPreferences;
  onPreferencesChange: (preferences: ReaderPreferences) => void;
  fontSizeRange: [number, number];
  fontSizeStep: number;
  /** Passed through to the appearance popover; see `ReaderSettings`. */
  canChooseColumns: boolean;
}

/**
 * The bar above the page: where you are, how to get somewhere else, and how to
 * leave.
 *
 * It carries no colours of its own. The reading theme decides what the page
 * looks like, and a bar that stayed white above a dark page would be the
 * brightest thing on the screen.
 */
export const ReaderChrome = ({
  title,
  positionLabel,
  onOpenToc,
  onClose,
  preferences,
  onPreferencesChange,
  fontSizeRange,
  fontSizeStep,
  canChooseColumns,
}: ReaderChromeProps) => {
  const [settingsAnchor, setSettingsAnchor] = useState<HTMLElement | null>(null);

  return (
    <Box
      component="header"
      {...chromeMarkerProps}
      sx={{
        flex: '0 0 auto',
        borderBottom: 1,
        borderColor: 'divider',
        color: 'inherit',
      }}
    >
      <Toolbar variant="dense" sx={{ gap: 1 }}>
        <Tooltip title="Contents">
          <IconButton onClick={onOpenToc} aria-label="Contents" color="inherit">
            <ChapterListIcon sx={{ fontSize: ICON_SIZE.ui }} />
          </IconButton>
        </Tooltip>

        <Stack sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h6" component="h1" noWrap title={title}>
            {title}
          </Typography>
          {positionLabel && (
            <Typography variant="body2" noWrap sx={{ opacity: 0.7 }}>
              {positionLabel}
            </Typography>
          )}
        </Stack>

        <Tooltip title="Appearance">
          <IconButton
            onClick={(event) => setSettingsAnchor(event.currentTarget)}
            aria-label="Appearance"
            color="inherit"
          >
            <PaletteIcon sx={{ fontSize: ICON_SIZE.ui }} />
          </IconButton>
        </Tooltip>

        <Tooltip title="Close reader">
          <IconButton onClick={onClose} aria-label="Close reader" color="inherit">
            <CloseIcon sx={{ fontSize: ICON_SIZE.ui }} />
          </IconButton>
        </Tooltip>
      </Toolbar>

      <ReaderSettings
        anchorEl={settingsAnchor}
        onClose={() => setSettingsAnchor(null)}
        preferences={preferences}
        onChange={onPreferencesChange}
        fontSizeRange={fontSizeRange}
        fontSizeStep={fontSizeStep}
        canChooseColumns={canChooseColumns}
      />
    </Box>
  );
};
