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
import { useEffect, useMemo, useRef } from 'react';

/**
 * The href the API gives a heading that links nowhere — a part title with
 * chapters under it, say. Such an entry is a label in the list, not a
 * destination.
 */
const UNLINKED_HREF = '#';

/** How far one level of nesting indents a chapter under its parent. */
const INDENT_PER_LEVEL = 2;

/**
 * The resource an href names, without the fragment or the query that follows
 * it. A contents entry may point into the middle of a chapter file; where the
 * reader *is* is only ever known by the file.
 */
const resourceOf = (href: string): string => href.split(/[#?]/)[0];

interface FlatEntry {
  entry: Link;
  depth: number;
}

/** Every entry of a contents tree, parents before their children. */
const flatten = (entries: Link[], depth: number): FlatEntry[] =>
  entries.flatMap((entry) => [
    { entry, depth },
    ...flatten(entry.children?.items ?? [], depth + 1),
  ]);

/**
 * Which entry of the contents the reader is currently inside, or `null` when
 * the book's contents do not name where they are.
 *
 * Resource-granular, because that is all a reading position reliably says: a
 * locator carries the file, and the sections within a file are the contents
 * page's own idea. Two rules turn the several entries that can share a file
 * into one answer.
 *
 * **Entries naming the whole file beat entries naming a section of it.** The
 * reader is *somewhere* in the chapter, and only the entry for the chapter
 * itself is true of wherever that is; picking one of its sections would be
 * marking a place nobody has been told they are at. Where every match names a
 * section — a book published as one long file, with its contents made of
 * fragments — there is no such entry and the first is the best available guess.
 *
 * **Then the deepest wins.** A part heading and the first chapter under it
 * routinely share an href, and the chapter is the more specific of the two.
 */
const currentEntry = (toc: Link[], currentHref: string | null): Link | null => {
  if (currentHref === null) return null;
  const resource = resourceOf(currentHref);
  const matches = flatten(toc, 0).filter(
    ({ entry }) => entry.href !== UNLINKED_HREF && resourceOf(entry.href) === resource
  );
  if (matches.length === 0) return null;

  const wholeResource = matches.filter(({ entry }) => !entry.href.includes('#'));
  const candidates = wholeResource.length > 0 ? wholeResource : matches;
  return candidates.reduce((deepest, candidate) =>
    candidate.depth > deepest.depth ? candidate : deepest
  ).entry;
};

interface TocDrawerProps {
  open: boolean;
  onClose: () => void;
  toc: Link[];
  onSelect: (link: Link) => void;
  /** The resource the reader is in, from the navigator's own current locator. */
  currentHref: string | null;
}

interface TocEntriesProps {
  entries: Link[];
  depth: number;
  onSelect: (link: Link) => void;
  /** The one entry to mark, compared by identity — both come from the manifest. */
  current: Link | null;
  currentRef: React.Ref<HTMLDivElement>;
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
export const TocDrawer = ({ open, onClose, toc, onSelect, currentHref }: TocDrawerProps) => {
  const current = useMemo(() => currentEntry(toc, currentHref), [toc, currentHref]);
  const currentRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // The drawer mounts its contents as it opens, so this runs with the marked
    // entry already laid out inside the scrolling panel. `nearest` because a
    // chapter that is on screen anyway should not be moved under the reader.
    if (open) currentRef.current?.scrollIntoView({ block: 'nearest' });
  }, [open, current]);

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
