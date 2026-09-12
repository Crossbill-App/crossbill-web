import { API_BASE_URL } from '@/api/base-url.ts';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import type { EbookTocEntry } from '@/components/reader/EbookReader.ts';
import { TocDrawer } from '@/components/reader/TocDrawer.tsx';
import { useEbookReader, type UseEbookReaderOptions } from '@/components/reader/useEbookReader.ts';
import { useReaderSession } from '@/components/reader/useReaderSession.ts';
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock.ts';
import { ChapterListIcon, CloseIcon, NextPageIcon, PreviousPageIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import {
  Box,
  Button,
  IconButton,
  Skeleton,
  Stack,
  Toolbar,
  Typography,
  type SxProps,
  type Theme,
} from '@mui/material';
import { useRef, useState } from 'react';

export interface ReaderShellProps {
  bookId: number;
  title: string;
  onClose: () => void;
  /** Both only for tests: a fake engine, and a watchdog short enough to wait for. */
  createReader?: UseEbookReaderOptions['createReader'];
  bootTimeoutMs?: number;
}

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
  backgroundColor: 'background.default',
  color: 'text.primary',
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
    sx={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', [edge]: 4, zIndex: 1 }}
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
  <Box sx={overlaySx}>
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
  createReader,
  bootTimeoutMs,
}: ReaderShellProps) => {
  // A fixed overlay never scrolls the body, which is what arms pull-to-refresh.
  useBodyScrollLock(true);
  const { status: sessionStatus, isRenewing } = useReaderSession(bookId);
  const host = useRef<HTMLDivElement | null>(null);
  const [isTocOpen, setIsTocOpen] = useState(false);
  const book = useEbookReader({
    host,
    manifestUrl: manifestUrlFor(bookId),
    enabled: sessionStatus === 'ready',
    holdPageTurns: isRenewing,
    createReader,
    bootTimeoutMs,
  });

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

  const goToTocEntry = (entry: EbookTocEntry) => {
    setIsTocOpen(false);
    book.goTo({ href: entry.href, type: entry.type, locations: {} });
  };

  return (
    <Box sx={overlaySx}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
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
              <Typography variant="body2" noWrap sx={{ color: 'text.secondary' }}>
                {pageLabel(position, book.pageCount, book.location?.locations.totalProgression)}
              </Typography>
            )}
          </Stack>
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

        {!isOpen && (
          <Stack
            aria-label="Loading the book"
            aria-busy="true"
            sx={{ position: 'absolute', inset: 0, p: 4, alignItems: 'center' }}
          >
            <Box sx={{ width: '100%', maxWidth: 640 }}>
              {Array.from({ length: 12 }, (_, index) => (
                <Skeleton key={index} height={28} width={index % 5 === 4 ? '55%' : '100%'} />
              ))}
            </Box>
          </Stack>
        )}

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
              ...(isRenewing && { backgroundColor: 'background.default', opacity: 0.9 }),
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
    </Box>
  );
};
