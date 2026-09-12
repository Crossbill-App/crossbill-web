import type { EbookTocEntry } from '@/components/reader/EbookReader.ts';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
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
import { Fragment, useCallback } from 'react';

/** The href a manifest gives a heading that links nowhere — a part title, say. */
const UNLINKED_HREF = '#';

/** How far one level of nesting indents a chapter under its parent. */
const INDENT_PER_LEVEL = 2;

interface TocDrawerProps {
  open: boolean;
  onClose: () => void;
  toc: EbookTocEntry[];
  onSelect: (entry: EbookTocEntry) => void;
  /** The entry the reader is in, as the engine resolved it. */
  currentHref: string | null;
}

interface TocEntriesProps {
  entries: EbookTocEntry[];
  depth: number;
  onSelect: (entry: EbookTocEntry) => void;
  currentHref: string | null;
  /** Attached to the marked entry, which scrolls it into view as it mounts. */
  currentRef: (node: HTMLDivElement | null) => void;
}

const TocEntries = ({ entries, depth, onSelect, currentHref, currentRef }: TocEntriesProps) => (
  <>
    {entries.map((entry, index) => {
      const isNavigable = entry.href !== UNLINKED_HREF;
      const isCurrent = entry.href === currentHref;
      return (
        <Fragment key={`${entry.href}-${index}`}>
          <ListItemButton
            ref={isCurrent ? currentRef : undefined}
            disabled={!isNavigable}
            selected={isCurrent}
            aria-current={isCurrent ? 'location' : undefined}
            onClick={() => onSelect(entry)}
            sx={{ pl: 2 + depth * INDENT_PER_LEVEL, borderRadius: 1 }}
          >
            <ListItemText
              primary={entry.title || 'Untitled'}
              slotProps={{ primary: { variant: 'body2' } }}
            />
          </ListItemButton>
          <TocEntries
            entries={entry.children}
            depth={depth + 1}
            onSelect={onSelect}
            currentHref={currentHref}
            currentRef={currentRef}
          />
        </Fragment>
      );
    })}
  </>
);

/** The book's contents as the manifest publishes them, with the chapter being read marked. */
export const TocDrawer = ({ open, onClose, toc, onSelect, currentHref }: TocDrawerProps) => {
  // A callback ref rather than an effect keyed on `open`: a temporary `Drawer`
  // renders nothing while closed and MUI's `Portal` returns null on its first
  // render, so such an effect fires in a commit where the list does not exist.
  const currentRef = useCallback((node: HTMLDivElement | null) => {
    node?.scrollIntoView({ block: 'center' });
  }, []);

  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      slotProps={{ paper: { 'aria-label': 'Contents' } }}
    >
      <Box sx={{ width: { xs: 280, sm: 340 } }} role="navigation" aria-label="Table of contents">
        <Stack
          direction="row"
          sx={{ alignItems: 'center', justifyContent: 'space-between', p: 2, pb: 1 }}
        >
          <SectionTitle gutterBottom={false}>Contents</SectionTitle>
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
              currentHref={currentHref}
              currentRef={currentRef}
            />
          </List>
        )}
      </Box>
    </Drawer>
  );
};
