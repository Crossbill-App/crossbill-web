import { HIGHLIGHT_DECORATION_GROUP } from '@/components/reader/decorations.ts';
import { ReaderChrome } from '@/components/reader/ReaderChrome.tsx';
import {
  DEFAULT_READER_PREFERENCES,
  readerPageColors,
  toEpubPreferences,
  type ReaderPreferences,
} from '@/components/reader/readerPreferences.ts';
import { TocDrawer } from '@/components/reader/TocDrawer.tsx';
import { useReaderPublication } from '@/components/reader/useReaderPublication.ts';
import { useReaderSession } from '@/components/reader/useReaderSession.ts';
import { NextPageIcon, PreviousPageIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, Button, IconButton, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import { EpubNavigator } from '@readium/navigator';
import type { Link, Locator } from '@readium/shared';
import { useCallback, useEffect, useRef, useState } from 'react';

/** Room in the margins for the page-turn buttons, so they never sit on the text. */
const PAGE_TURN_GUTTER = 48;

/**
 * What the font-size control offers before there is a navigator to ask.
 *
 * Replaced by `EpubPreferencesEditor`'s own numbers as soon as one has loaded,
 * which is before the settings popover can be opened at all.
 */
const DEFAULT_FONT_SIZE_BOUNDS: { range: [number, number]; step: number } = {
  range: [0.7, 4],
  step: 0.05,
};

interface ReaderShellProps {
  bookId: number;
  title: string;
  onClose: () => void;
}

/** Resolves once the element has a real box, or immediately if it already has one. */
const whenSized = (element: HTMLElement) =>
  new Promise<void>((resolve) => {
    if (element.clientWidth > 0 && element.clientHeight > 0) {
      resolve();
      return;
    }
    const observer = new ResizeObserver(() => {
      if (element.clientWidth > 0 && element.clientHeight > 0) {
        observer.disconnect();
        resolve();
      }
    });
    observer.observe(element);
  });

/**
 * The reader itself: one `EpubNavigator`, the chrome around it, and the two
 * credentials that let it read a book.
 *
 * Three things about the lifecycle are load-bearing.
 *
 * **The container is sized before the navigator sees it.** Readium gives its
 * iframes `position: absolute` and no dimensions at all, and sizes the
 * container from the *parent* it observes — so a navigator built against an
 * unsized element renders every frame at the browser's default 300x150 and
 * never recovers. The viewport below is a fixed, flex-sized element; the
 * navigator's own container is created inside it only once it measures
 * non-zero.
 *
 * **The navigator lives in a ref, never in state.** It is a mutable object
 * with a DOM subtree under it; putting it in state would re-render the tree
 * that owns that subtree on every page turn.
 *
 * **Boots are serialised.** React 19's StrictMode mounts effects twice, and
 * `destroy()` is asynchronous: without chaining, the first navigator's
 * teardown lands in the middle of the second one's load and takes its frames
 * with it.
 */
export const ReaderShell = ({ bookId, title, onClose }: ReaderShellProps) => {
  const theme = useTheme();
  const sessionStatus = useReaderSession(bookId);
  const { status: publicationStatus, publication, positions } = useReaderPublication(bookId);

  const viewportRef = useRef<HTMLDivElement | null>(null);
  const navigatorRef = useRef<EpubNavigator | null>(null);
  const bootRef = useRef<Promise<unknown>>(Promise.resolve());

  const [isPageVisible, setIsPageVisible] = useState(false);
  const [locator, setLocator] = useState<Locator | null>(null);
  const [isTocOpen, setIsTocOpen] = useState(false);
  const [preferences, setPreferences] = useState<ReaderPreferences>(DEFAULT_READER_PREFERENCES);
  // Copied out of the navigator's own `EpubPreferencesEditor` once it exists,
  // rather than read off the instance while rendering: the editor is a live
  // object hanging off a ref, and a ref is not something a render may consult.
  const [fontSizeBounds, setFontSizeBounds] = useState(DEFAULT_FONT_SIZE_BOUNDS);

  const goForward = useCallback(() => navigatorRef.current?.goForward(true, () => {}), []);
  const goBackward = useCallback(() => navigatorRef.current?.goBackward(true, () => {}), []);

  // Stable, because both page turns read the navigator out of a ref. That is
  // what lets the same handler be bound to each publication frame for its whole
  // life without the navigator having to be rebuilt.
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight') goForward();
      if (event.key === 'ArrowLeft') goBackward();
    },
    [goForward, goBackward]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const isReady =
    sessionStatus === 'ready' &&
    publicationStatus === 'ready' &&
    !!publication &&
    positions !== undefined;

  useEffect(() => {
    if (!isReady) return;
    const viewport = viewportRef.current;
    if (!viewport) return;

    // An AbortController rather than a plain flag: this boot is a chain of
    // awaits, and every step has to be able to ask whether it still matters.
    const teardown = new AbortController();
    // Read through a call rather than the property: a narrowed flag is not what
    // this is, and the compiler would happily prove a later check redundant.
    const isStale = () => teardown.signal.aborted;
    let epubNavigator: EpubNavigator | null = null;
    let container: HTMLDivElement | null = null;

    const boot = bootRef.current.then(async () => {
      if (isStale()) return;
      await whenSized(viewport);
      if (isStale()) return;

      container = document.createElement('div');
      container.style.position = 'relative';
      container.style.height = '100%';
      container.style.margin = '0 auto';
      viewport.appendChild(container);

      epubNavigator = new EpubNavigator(
        container,
        publication,
        {
          /**
           * One frame of the publication is in the DOM and scriptable.
           *
           * The seam M3.2 hangs its highlights on: decorations are applied per
           * frame, so this is where a newly loaded resource gets the ones that
           * belong to it. Today it only reveals the page and gives the frame
           * the arrow keys, which a same-origin iframe does not bubble up on
           * its own.
           */
          frameLoaded: (frameWindow: Window) => {
            frameWindow.addEventListener('keydown', handleKeyDown);
            setIsPageVisible(true);
          },
          positionChanged: (current: Locator) => setLocator(current),
          /**
           * The reader selected text in the book.
           *
           * `selection.locator` is populated by the navigator — the
           * browser-selection to Locator half of ADR-0004 §2's write path.
           * M4.1 converts it to an `XPointRange` and offers to highlight it;
           * until then, selecting text does what selecting text does.
           */
          textSelected: () => {},
          timelineItemChanged: () => {},
          tap: () => true,
          click: () => true,
          zoom: () => {},
          miscPointer: () => {},
          scroll: () => {},
          customEvent: () => {},
          handleLocator: () => false,
          contentProtection: () => {},
          contextMenu: () => {},
          peripheral: () => {},
        },
        positions,
        undefined,
        { preferences: toEpubPreferences(theme, preferences), defaults: {} }
      );

      // Reserved now so the group exists before anything draws into it, and so
      // that a decoration activated in M3.2 already has somewhere to arrive.
      epubNavigator.registerDecorationObserver(HIGHLIGHT_DECORATION_GROUP, {});

      navigatorRef.current = epubNavigator;
      await epubNavigator.load();
      // The frame pool is laid out from the container's measurements, which
      // are only final after the browser has painted the frames it just added.
      await new Promise((resolve) => requestAnimationFrame(resolve));
      await epubNavigator.resizeHandler();
      if (isStale()) return;
      const fontSize = epubNavigator.preferencesEditor.fontSize;
      setFontSizeBounds({ range: fontSize.supportedRange, step: fontSize.step });
      setLocator(epubNavigator.currentLocator);
    });

    bootRef.current = boot.catch(() => undefined);

    return () => {
      teardown.abort();
      setIsPageVisible(false);
      navigatorRef.current = null;
      // Chained rather than immediate: destroying a navigator that is still
      // loading leaves its frames behind in the container.
      bootRef.current = boot
        .then(() => epubNavigator?.destroy())
        .then(() => container?.remove())
        .catch(() => undefined);
    };
    // `preferences` is deliberately absent: it seeds the navigator here and is
    // submitted to the live one below. Listing it would rebuild the reader,
    // and the book would jump back to page one on every font-size nudge.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReady, publication, positions, theme, handleKeyDown]);

  useEffect(() => {
    if (!isPageVisible) return;
    void navigatorRef.current?.submitPreferences(toEpubPreferences(theme, preferences));
  }, [isPageVisible, preferences, theme]);

  const goToTocEntry = useCallback((link: Link) => {
    setIsTocOpen(false);
    navigatorRef.current?.goLink(link, true, () => {});
  }, []);

  const pageColors = readerPageColors(theme, preferences.theme);
  const page = locator?.locations.position;
  const progression = locator?.locations.totalProgression;
  const pageCount = positions?.length ?? 0;
  const positionLabel =
    pageCount > 0 && page !== undefined
      ? `Page ${page} of ${pageCount}` +
        (progression === undefined ? '' : ` · ${Math.round(progression * 100)}%`)
      : null;

  if (publicationStatus === 'missing' || publicationStatus === 'error') {
    return (
      <ReaderMessage onClose={onClose}>
        {publicationStatus === 'missing'
          ? 'This book has no EPUB file, so there is nothing to read here yet. Upload one to read it in the browser.'
          : 'The book could not be opened. Please try again later.'}
      </ReaderMessage>
    );
  }

  if (sessionStatus === 'error') {
    return (
      <ReaderMessage onClose={onClose}>
        The reader could not start a session for this book. Please try again later.
      </ReaderMessage>
    );
  }

  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: (t) => t.zIndex.appBar + 1,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: pageColors.background,
        color: pageColors.text,
        transition: (t) => t.transitions.create(['background-color', 'color']),
      }}
    >
      <ReaderChrome
        title={title}
        positionLabel={positionLabel}
        onOpenToc={() => setIsTocOpen(true)}
        onClose={onClose}
        preferences={preferences}
        onPreferencesChange={setPreferences}
        fontSizeRange={fontSizeBounds.range}
        fontSizeStep={fontSizeBounds.step}
      />

      <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
        <PageTurnButton edge="left" onClick={goBackward} />
        <PageTurnButton edge="right" onClick={goForward} />

        {/* The element the navigator measures. Its own container is created
            inside it once it has a box, and the frames Readium appends are
            given the dimensions the library does not set for itself. */}
        <Box
          ref={viewportRef}
          data-testid="reader-viewport"
          sx={{
            height: '100%',
            px: `${PAGE_TURN_GUTTER}px`,
            visibility: isPageVisible ? 'visible' : 'hidden',
            '& .readium-navigator-iframe': {
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              border: 'none',
            },
          }}
        />

        {!isPageVisible && (
          <Stack
            aria-label="Loading the book"
            aria-busy="true"
            sx={{ position: 'absolute', inset: 0, p: 4, gap: 1.5, alignItems: 'center' }}
          >
            <Box sx={{ width: '100%', maxWidth: 640 }}>
              {Array.from({ length: 12 }, (_, index) => index).map((index) => (
                <Skeleton key={index} height={28} width={index % 5 === 4 ? '55%' : '100%'} />
              ))}
            </Box>
          </Stack>
        )}
      </Box>

      <TocDrawer
        open={isTocOpen}
        onClose={() => setIsTocOpen(false)}
        toc={publication?.toc?.items ?? []}
        onSelect={goToTocEntry}
      />
    </Box>
  );
};

interface PageTurnButtonProps {
  edge: 'left' | 'right';
  onClick: () => void;
}

const PageTurnButton = ({ edge, onClick }: PageTurnButtonProps) => (
  <IconButton
    onClick={onClick}
    color="inherit"
    aria-label={edge === 'left' ? 'Previous page' : 'Next page'}
    sx={{
      position: 'absolute',
      top: '50%',
      transform: 'translateY(-50%)',
      [edge]: 4,
      zIndex: 1,
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
}

/** The whole-viewport stand-in for a book that cannot be read. */
const ReaderMessage = ({ children, onClose }: ReaderMessageProps) => (
  <Box
    sx={{
      position: 'fixed',
      inset: 0,
      zIndex: (t) => t.zIndex.appBar + 1,
      backgroundColor: 'background.default',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      p: 3,
    }}
  >
    <Stack spacing={3} sx={{ maxWidth: 480, alignItems: 'center', textAlign: 'center' }}>
      <Typography variant="body1" sx={{ color: 'text.secondary' }}>
        {children}
      </Typography>
      <Button variant="outlined" onClick={onClose}>
        Back to book
      </Button>
    </Stack>
  </Box>
);
