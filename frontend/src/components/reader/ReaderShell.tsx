import { API_BASE_URL } from '@/api/base-url.ts';
import type { Highlight } from '@/api/generated/model';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { highlightIdFrom } from '@/components/reader/decorations.ts';
import type { EbookTocEntry } from '@/components/reader/EbookReader.ts';
import {
  landingOfAJump,
  tocEntryLocation,
  type MissedJump,
} from '@/components/reader/jumpFallback.ts';
import { ReaderLoading } from '@/components/reader/ReaderLoading.tsx';
import { readerPageColors, toEbookAppearance } from '@/components/reader/readerPreferences.ts';
import { ReaderSettings } from '@/components/reader/ReaderSettings.tsx';
import { SelectionPopover } from '@/components/reader/SelectionPopover.tsx';
import { TocDrawer } from '@/components/reader/TocDrawer.tsx';
import { useEbookReader, type UseEbookReaderOptions } from '@/components/reader/useEbookReader.ts';
import { useHighlightCreation } from '@/components/reader/useHighlightCreation.ts';
import { useHighlightDecorations } from '@/components/reader/useHighlightDecorations.ts';
import { useReaderLanding } from '@/components/reader/useReaderLanding.ts';
import { useReaderPreferences } from '@/components/reader/useReaderPreferences.ts';
import { useReaderSession } from '@/components/reader/useReaderSession.ts';
import { useReadingPositionWriter } from '@/components/reader/useReadingPositionWriter.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock.ts';
import {
  ChapterListIcon,
  CloseIcon,
  NextPageIcon,
  PaletteIcon,
  PreviousPageIcon,
} from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import {
  alpha,
  Box,
  Button,
  IconButton,
  Stack,
  Toolbar,
  Typography,
  useTheme,
  type SxProps,
  type Theme,
} from '@mui/material';
import { useEffect, useMemo, useRef, useState } from 'react';

export interface ReaderShellProps {
  bookId: number;
  title: string;
  onClose: () => void;
  /** The book's highlights, `undefined` until the book-details query has answered. */
  highlights?: Highlight[];
  /** A highlight the reader tapped on the page. */
  onOpenHighlight?: (highlightId: number) => void;
  /** The highlight to open the book at; only its value at mount counts. */
  highlightId?: number;
  /** All four only for tests: a fake engine, and waits short enough to sit through. */
  createReader?: UseEbookReaderOptions['createReader'];
  bootTimeoutMs?: number;
  writeDebounceMs?: number;
  heartbeatMs?: number;
}

/** Said once, over the open book, for a place that could not be restored. */
const LOST_THE_BOOKMARK = "Couldn't restore your last position, so the book opened at the start.";

/** Said once, over the open book, for a highlight whose passage could not be reached. */
const MISSED_JUMP_APOLOGIES: Record<MissedJump, string> = {
  chapter:
    "Couldn't find this highlight's exact place, so the book opened at the start of its chapter.",
  start: "Couldn't find this highlight's place, so the book opened at the start.",
};

/** The width the page-turn buttons need beside the text on anything but a phone. */
const PAGE_TURN_GUTTER = '48px';

/** Readium's own page gutter is horizontal only, so the air above and below is ours to add. */
const READING_SURFACE_INSET = 2;

const pageLabel = (page: number, pageCount: number, progression: number | undefined) =>
  `Page ${page} of ${pageCount}` +
  (progression === undefined ? '' : ` · ${Math.round(progression * 100)}%`);

const overlaySx: SxProps<Theme> = {
  position: 'fixed',
  inset: 0,
  zIndex: (t) => t.zIndex.appBar + 1,
  display: 'flex',
  flexDirection: 'column',
};

const manifestUrlFor = (bookId: number) =>
  new URL(`${API_BASE_URL}/api/v1/readium/books/${bookId}/manifest.json`, window.location.origin)
    .href;

interface PageTurnButtonProps {
  edge: 'left' | 'right';
  onClick: () => void;
  disabled: boolean;
}

const PageTurnButton = ({ edge, onClick, disabled }: PageTurnButtonProps) => (
  <IconButton
    onClick={onClick}
    disabled={disabled}
    color="inherit"
    aria-label={edge === 'left' ? 'Previous page' : 'Next page'}
    sx={{
      position: 'absolute',
      top: '50%',
      transform: 'translateY(-50%)',
      [edge]: 4,
      zIndex: 1,
      // Gone on a phone, where they cover the page they turn and swiping is
      // the gesture at hand; the gutter they need goes with them.
      display: { xs: 'none', sm: 'inline-flex' },
    }}
  >
    {edge === 'left' ? (
      <PreviousPageIcon sx={{ fontSize: ICON_SIZE.prominent }} />
    ) : (
      <NextPageIcon sx={{ fontSize: ICON_SIZE.prominent }} />
    )}
  </IconButton>
);

interface ReaderMessageProps {
  children: string;
  onClose: () => void;
  /** Offered only where trying again could plausibly work. */
  onRetry?: () => void;
}

const ReaderMessage = ({ children, onClose, onRetry }: ReaderMessageProps) => (
  <Box sx={{ ...overlaySx, backgroundColor: 'background.default', color: 'text.primary' }}>
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        p: 3,
        textAlign: 'center',
      }}
    >
      <Typography>{children}</Typography>
      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={onClose}>
          Back to book
        </Button>
        {onRetry && (
          <Button variant="contained" onClick={onRetry}>
            Try again
          </Button>
        )}
      </Stack>
    </Box>
  </Box>
);

/** The reader's full-viewport frame: a title bar, a way out, and the book. */
export const ReaderShell = ({
  bookId,
  title,
  onClose,
  highlights,
  onOpenHighlight,
  highlightId,
  createReader,
  bootTimeoutMs,
  writeDebounceMs,
  heartbeatMs,
}: ReaderShellProps) => {
  // A fixed overlay never scrolls the body, which is what arms pull-to-refresh.
  useBodyScrollLock(true);
  const { status: sessionStatus, isRenewing } = useReaderSession(bookId);
  const host = useRef<HTMLDivElement | null>(null);
  const [isTocOpen, setIsTocOpen] = useState(false);
  const [preferences, setPreferences] = useReaderPreferences();
  const [appearanceAnchor, setAppearanceAnchor] = useState<Element | null>(null);
  const theme = useTheme();
  const pageColors = readerPageColors(theme, preferences.pageColor);
  // A new object every render would submit the same appearance to the engine
  // again on every render, which is not a cost the engine skips.
  const appearance = useMemo(() => toEbookAppearance(theme, preferences), [theme, preferences]);
  const { record } = useReadingPositionWriter(bookId, { writeDebounceMs, heartbeatMs });
  // Latched, so that nothing done to the address after the book opens can move it.
  const [target] = useState(highlightId ?? null);
  const landing = useReaderLanding(bookId, target);
  const placedHighlights = useHighlightDecorations(bookId, highlights);
  const creation = useHighlightCreation(bookId);
  const decorations = useMemo(
    () => [...placedHighlights, ...creation.standIns],
    [placedHighlights, creation.standIns]
  );
  const missedJump = useRef<MissedJump | null>(null);
  const book = useEbookReader({
    host,
    manifestUrl: manifestUrlFor(bookId),
    // A navigator takes its initial position once, at construction, so the book
    // waits for the answer rather than opening somewhere and being corrected.
    enabled: sessionStatus === 'ready' && landing !== undefined,
    holdPageTurns: isRenewing,
    appearance,
    initialLocation: landing?.locator ?? null,
    decorations,
    createReader,
    bootTimeoutMs,
    onLocationReported: record,
    onDecorationActivated: (id) => {
      const tapped = highlightIdFrom(id);
      if (tapped !== null) onOpenHighlight?.(tapped);
    },
    // On to the passage, which opening at its locator can leave a page short of, or else to
    // its chapter; what was missed is kept for the apology once the book is on screen.
    finishLanding:
      target === null
        ? undefined
        : (opened) => {
            const jump = landingOfAJump(landing?.locator ?? null, opened, landing?.chapter ?? null);
            missedJump.current = jump.missed;
            return jump.destination;
          },
  });

  const { showSnackbar } = useSnackbar();
  const apologised = useRef(false);
  useEffect(() => {
    if (apologised.current || book.status !== 'open' || !landing) return;
    // `'start'` with a place still on offer covers both remaining failures: a
    // locator this edition cannot place, and one the navigator refused outright
    // and which the retry therefore stopped offering.
    const lost = landing.lost || (landing.locator !== null && book.landedAt === 'start');
    const message =
      target === null
        ? lost
          ? LOST_THE_BOOKMARK
          : null
        : missedJump.current && MISSED_JUMP_APOLOGIES[missedJump.current];
    if (!message) return;
    apologised.current = true;
    showSnackbar(message, 'info');
  }, [book.status, book.landedAt, landing, target, showSnackbar]);

  if (sessionStatus === 'error') {
    return (
      <ReaderMessage onClose={onClose}>
        The reader could not start a session for this book. Please try again later.
      </ReaderMessage>
    );
  }
  if (book.status === 'missing') {
    return (
      <ReaderMessage onClose={onClose}>
        This book has no EPUB file, so there is nothing to read here yet. Upload one to read it in
        the browser.
      </ReaderMessage>
    );
  }
  if (book.status === 'error') {
    return (
      <ReaderMessage onClose={onClose} onRetry={book.retry}>
        The book could not be opened. Please try again later.
      </ReaderMessage>
    );
  }
  if (book.status === 'timeout') {
    return (
      <ReaderMessage onClose={onClose} onRetry={book.retry}>
        This book could not be opened in the reader.
      </ReaderMessage>
    );
  }

  const isOpen = book.status === 'open';
  const pageTurnsDisabled = isRenewing || !isOpen;
  const position = book.location?.locations.position;

  const highlightSelection = () => {
    const location = book.selection?.location;
    book.clearSelection();
    if (location) creation.create(location);
  };

  const goToTocEntry = (entry: EbookTocEntry) => {
    setIsTocOpen(false);
    book.goTo(tocEntryLocation(entry));
  };

  return (
    <Box
      sx={{
        ...overlaySx,
        backgroundColor: pageColors.background,
        color: pageColors.text,
        transition: (t) => t.transitions.create(['background-color', 'color']),
      }}
    >
      <Box sx={{ borderBottom: 1, borderColor: alpha(pageColors.text, 0.12) }}>
        <Toolbar variant="dense" sx={{ gap: 1 }}>
          <IconButtonWithTooltip
            label="Contents"
            onClick={() => setIsTocOpen(true)}
            disabled={!isOpen}
            edge="start"
            icon={<ChapterListIcon sx={{ fontSize: ICON_SIZE.ui }} />}
          />
          <Stack sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h6" component="h1" noWrap>
              {title}
            </Typography>
            {book.pageCount > 0 && position !== undefined && (
              // 0.7 of the page's own text, which is 6.3:1 on the light page
              // and 8.4:1 on the dark one; body text needs 4.5:1.
              <Typography variant="body2" noWrap sx={{ color: alpha(pageColors.text, 0.7) }}>
                {pageLabel(position, book.pageCount, book.location?.locations.totalProgression)}
              </Typography>
            )}
          </Stack>
          <IconButtonWithTooltip
            label="Appearance"
            onClick={(event) => setAppearanceAnchor(event.currentTarget)}
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

      <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
        <PageTurnButton edge="left" onClick={book.previous} disabled={pageTurnsDisabled} />
        <PageTurnButton edge="right" onClick={book.next} disabled={pageTurnsDisabled} />

        {/* Hidden rather than unmounted: the engine measures this box to lay
            the book out, and a box that is not there has no size to measure. */}
        <Box
          ref={host}
          sx={{
            height: '100%',
            px: { xs: 0, sm: PAGE_TURN_GUTTER },
            py: READING_SURFACE_INSET,
            visibility: isOpen ? 'visible' : 'hidden',
          }}
        />

        {!isOpen && <ReaderLoading />}

        {/* Mounted for as long as the book is: a live region that appears
            together with its text announces nothing. */}
        {isOpen && (
          <Stack
            aria-live="polite"
            sx={{
              position: 'absolute',
              inset: 0,
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: isRenewing ? 'auto' : 'none',
              ...(isRenewing && { backgroundColor: pageColors.background, opacity: 0.9 }),
            }}
          >
            {isRenewing && <Typography variant="body2">Reconnecting…</Typography>}
          </Stack>
        )}
      </Box>

      <TocDrawer
        open={isTocOpen}
        onClose={() => setIsTocOpen(false)}
        toc={book.toc}
        onSelect={goToTocEntry}
        currentHref={book.currentTocHref}
      />

      {book.fontSizeRange && (
        <ReaderSettings
          anchorEl={appearanceAnchor}
          onClose={() => setAppearanceAnchor(null)}
          preferences={preferences}
          onChange={setPreferences}
          fontSizeRange={book.fontSizeRange}
        />
      )}

      <SelectionPopover
        selection={book.selection}
        onHighlight={highlightSelection}
        onCancel={book.clearSelection}
      />
    </Box>
  );
};
