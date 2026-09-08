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
import { useCallback } from 'react';

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
  /**
   * The entry the reader is currently in, resolved by Readium's own
   * `Timeline.tocEntryFor` — see `ReaderShell`. Compared by identity, because
   * that is the same `Link` object this tree is rendered from.
   */
  current: Link | null;
}

interface TocEntriesProps {
  entries: Link[];
  depth: number;
  onSelect: (link: Link) => void;
  current: Link | null;
  /** Attached to the marked entry, which scrolls it into view as it mounts. */
  currentRef: (node: HTMLDivElement | null) => void;
}

const TocEntries = ({ entries, depth, onSelect, current, currentRef }: TocEntriesProps) => (
  <>
    {entries.map((entry, index) => {
      const isNavigable = entry.href !== UNLINKED_HREF;
      const isCurrent = entry === current;
      return (
        <Box key={`${entry.href}-${index}`}>
          <ListItemButton
            ref={isCurrent ? currentRef : undefined}
            disabled={!isNavigable}
            selected={isCurrent}
            aria-current={isCurrent ? 'location' : undefined}
            onClick={() => onSelect(entry)}
            sx={{ pl: 2 + depth * INDENT_PER_LEVEL, borderRadius: 1 }}
          >
            <ListItemText
              primary={entry.title ?? 'Untitled'}
              slotProps={{ primary: { variant: 'body2' } }}
            />
          </ListItemButton>
          {entry.children && (
            <TocEntries
              entries={entry.children.items}
              depth={depth + 1}
              onSelect={onSelect}
              current={current}
              currentRef={currentRef}
            />
          )}
        </Box>
      );
    })}
  </>
);

/**
 * The book's table of contents, as the manifest publishes it, with the chapter
 * being read marked in it.
 *
 * Nesting is preserved rather than flattened: an EPUB's own contents page is
 * how its author thought the book was shaped, and a part with six chapters
 * under it reads very differently as a flat list of seven.
 *
 * A long book's contents open scrolled to where the reader is, because a list
 * of ninety chapters that always opens at chapter one is a list you have to
 * search to find yourself in.
 */
export const TocDrawer = ({ open, onClose, toc, onSelect, current }: TocDrawerProps) => {
  /**
   * Scrolls the marked entry into view as it attaches.
   *
   * A callback ref rather than an effect, and that is the whole point. A
   * temporary `Drawer` renders nothing at all while it is closed, and MUI's
   * `Portal` returns `null` on its first render — it only has a container to
   * render into once its own layout effect has run. So the commit in which
   * `open` becomes true mounts no list at all, and an effect keyed on `open`
   * fires in exactly that commit, with nothing to scroll to; the commit that
   * does mount the list changes none of that effect's dependencies, so it
   * never runs again. The ref, by contrast, fires when the entry itself
   * arrives, which is the first moment the question can be answered.
   *
   * Stable, so it fires on the marked entry appearing and moving rather than
   * on every render of the list.
   */
  const currentRef = useCallback((node: HTMLDivElement | null) => {
    node?.scrollIntoView({ block: 'center' });
  }, []);

  return (
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
            <TocEntries
              entries={toc}
              depth={0}
              onSelect={onSelect}
              current={current}
              currentRef={currentRef}
            />
          </List>
        )}
      </Box>
    </Drawer>
  );
};
