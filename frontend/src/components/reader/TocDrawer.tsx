import { chromeMarkerProps } from '@/components/reader/chromeMarker.ts';
import { CloseIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import {
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material';
import type { Link } from '@readium/shared';

/**
 * The href the API gives a heading that links nowhere — a part title with
 * chapters under it, say. Such an entry is a label in the list, not a
 * destination.
 */
const UNLINKED_HREF = '#';

/** How far one level of nesting indents a chapter under its parent. */
const INDENT_PER_LEVEL = 2;

interface TocDrawerProps {
  open: boolean;
  onClose: () => void;
  toc: Link[];
  onSelect: (link: Link) => void;
}

interface TocEntriesProps {
  entries: Link[];
  depth: number;
  onSelect: (link: Link) => void;
}

const TocEntries = ({ entries, depth, onSelect }: TocEntriesProps) => (
  <>
    {entries.map((entry, index) => {
      const isNavigable = entry.href !== UNLINKED_HREF;
      return (
        <Box key={`${entry.href}-${index}`}>
          <ListItemButton
            disabled={!isNavigable}
            onClick={() => onSelect(entry)}
            sx={{ pl: 2 + depth * INDENT_PER_LEVEL, borderRadius: 1 }}
          >
            <ListItemText
              primary={entry.title ?? 'Untitled'}
              slotProps={{ primary: { variant: 'body2' } }}
            />
          </ListItemButton>
          {entry.children && (
            <TocEntries entries={entry.children.items} depth={depth + 1} onSelect={onSelect} />
          )}
        </Box>
      );
    })}
  </>
);

/**
 * The book's table of contents, as the manifest publishes it.
 *
 * Nesting is preserved rather than flattened: an EPUB's own contents page is
 * how its author thought the book was shaped, and a part with six chapters
 * under it reads very differently as a flat list of seven.
 */
export const TocDrawer = ({ open, onClose, toc, onSelect }: TocDrawerProps) => (
  <Drawer anchor="left" open={open} onClose={onClose}>
    <Box
      {...chromeMarkerProps}
      sx={{ width: { xs: 280, sm: 340 } }}
      role="navigation"
      aria-label="Table of contents"
    >
      <Stack
        direction="row"
        sx={{ alignItems: 'center', justifyContent: 'space-between', p: 2, pb: 1 }}
      >
        <Typography variant="sectionTitle" component="h2">
          Contents
        </Typography>
        <IconButton onClick={onClose} aria-label="Close contents" size="small">
          <CloseIcon sx={{ fontSize: ICON_SIZE.ui }} />
        </IconButton>
      </Stack>
      {toc.length === 0 ? (
        <Typography variant="body2" sx={{ color: 'text.secondary', px: 2, pb: 2 }}>
          This book has no table of contents.
        </Typography>
      ) : (
        <List sx={{ pb: 2 }}>
          <TocEntries entries={toc} depth={0} onSelect={onSelect} />
        </List>
      )}
    </Box>
  </Drawer>
);
