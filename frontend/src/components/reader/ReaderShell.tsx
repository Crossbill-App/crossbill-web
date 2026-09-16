import { API_BASE_URL } from '@/api/base-url.ts';
import type { Highlight } from '@/api/generated/model';
import { isAnyDialogOpen } from '@/components/dialogs/dialogStack.ts';
import { heldPassageDecoration, highlightIdFrom } from '@/components/reader/decorations.ts';
import type { EbookTocEntry } from '@/components/reader/EbookReader.ts';
import { ExtensionBar } from '@/components/reader/ExtensionBar.tsx';
import { landingOfAJump } from '@/components/reader/jumpFallback.ts';
import { ReaderMessage } from '@/components/reader/ReaderMessage.tsx';
import { overlaySx } from '@/components/reader/readerOverlay.ts';
import { readerPageColors, toEbookAppearance } from '@/components/reader/readerPreferences.ts';
import { ReaderSettings } from '@/components/reader/ReaderSettings.tsx';
import { ReaderToolbar } from '@/components/reader/ReaderToolbar.tsx';
import { ReadingSurface } from '@/components/reader/ReadingSurface.tsx';
import { SelectionPopover } from '@/components/reader/SelectionPopover.tsx';
import { tocEntryLocation } from '@/components/reader/toc.ts';
import { TocDrawer } from '@/components/reader/TocDrawer.tsx';
import { useEbookReader, type UseEbookReaderOptions } from '@/components/reader/useEbookReader.ts';
import { useHighlightCreation } from '@/components/reader/useHighlightCreation.ts';
import { useHighlightDecorations } from '@/components/reader/useHighlightDecorations.ts';
import { useLandingApology } from '@/components/reader/useLandingApology.ts';
import { useReaderLanding } from '@/components/reader/useReaderLanding.ts';
import { useReaderPreferences } from '@/components/reader/useReaderPreferences.ts';
import { useReaderSession } from '@/components/reader/useReaderSession.ts';
import { useReadingPositionWriter } from '@/components/reader/useReadingPositionWriter.ts';
import { useSelectionWorkflow } from '@/components/reader/useSelectionWorkflow.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock.ts';
import { Box, useTheme } from '@mui/material';
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

/** Said over the open book for a tap that landed in a chapter the passage cannot reach. */
const ONE_CHAPTER_ONLY = 'A highlight has to stay inside one chapter.';

const manifestUrlFor = (bookId: number) =>
  new URL(`${API_BASE_URL}/api/v1/readium/books/${bookId}/manifest.json`, window.location.origin)
    .href;

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
  const { seed, moved } = useReadingPositionWriter(bookId, { writeDebounceMs, heartbeatMs });
  // Latched, so that nothing done to the address after the book opens can move it.
  const [target] = useState(highlightId ?? null);
  const landing = useReaderLanding(bookId, target);
  const placedHighlights = useHighlightDecorations(bookId, highlights);
  const creation = useHighlightCreation(bookId);
  const { showSnackbar } = useSnackbar();
  const book = useEbookReader({
    host,
    manifestUrl: manifestUrlFor(bookId),
    // A navigator takes its initial position once, at construction, so the book
    // waits for the answer rather than opening somewhere and being corrected.
    enabled: sessionStatus === 'ready' && landing !== undefined,
    // Held while a lapsed cookie is being replaced: a page fetched with a dead
    // credential comes back blank. Held too while a dialog is up, because Readium
    // steps aside only while focus is on what it counts as interactive, and a
    // dialog can drop focus to its own container, which it does not count.
    canTurnPage: () => !isRenewing && !isAnyDialogOpen(),
    appearance,
    initialLocation: landing?.locator ?? null,
    createReader,
    bootTimeoutMs,
    on: {
      arrivedAt: seed,
      movedTo: moved,
      decorationActivated: (id) => {
        const tapped = highlightIdFrom(id);
        if (tapped !== null) onOpenHighlight?.(tapped);
      },
      // The engine keeps the remembered start, so the bar stays up for a tap in its chapter.
      selectionExtensionRefused: () => showSnackbar(ONE_CHAPTER_ONLY, 'info'),
    },
    // On to the passage, which opening at its locator can leave a page short of, or else to
    // its chapter.
    finishLanding:
      target === null
        ? undefined
        : (opened) =>
            landingOfAJump(landing?.locator ?? null, opened, landing?.chapter ?? null).destination,
  });

  const workflow = useSelectionWorkflow(book, creation);
  const decorations = useMemo(
    () => [
      ...placedHighlights,
      ...creation.standIns,
      ...(workflow.heldPassage ? [heldPassageDecoration(workflow.heldPassage)] : []),
    ],
    [placedHighlights, creation.standIns, workflow.heldPassage]
  );
  // Pushed to whichever reader is on screen, the one it opened with or a retry's.
  const applyDecorations = book.applyDecorations;
  useEffect(() => applyDecorations(decorations), [applyDecorations, decorations]);

  // The preference store no longer knows the engine's range, so a size stored
  // outside it — which happens only when the range changed between versions —
  // is corrected here, where the engine has said what it honours, at the cost
  // of one reflow in that rare case.
  const fontSizeRange = book.fontSizeRange;
  useEffect(() => {
    if (!fontSizeRange) return;
    const [min, max] = fontSizeRange;
    const honoured = Math.min(Math.max(preferences.fontSize, min), max);
    if (honoured !== preferences.fontSize) {
      setPreferences((current) => ({ ...current, fontSize: honoured }));
    }
  }, [fontSizeRange, preferences.fontSize, setPreferences]);

  useLandingApology(book, landing, target);

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
  const position = book.location?.locations.position;

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
      <ReaderToolbar
        title={title}
        page={position}
        pageCount={book.pageCount}
        progression={book.location?.locations.totalProgression}
        isOpen={isOpen}
        colors={pageColors}
        onOpenContents={() => setIsTocOpen(true)}
        onOpenAppearance={setAppearanceAnchor}
        onClose={onClose}
      />

      <ReadingSurface
        host={host}
        isOpen={isOpen}
        isRenewing={isRenewing}
        colors={pageColors}
        onNext={book.next}
        onPrevious={book.previous}
        notice={
          workflow.isExtending && (
            <ExtensionBar colors={pageColors} onCancel={workflow.stopExtending} />
          )
        }
      />

      <TocDrawer
        open={isTocOpen}
        onClose={() => setIsTocOpen(false)}
        toc={book.toc}
        onSelect={goToTocEntry}
        currentHref={book.currentTocHref}
      />

      {fontSizeRange && (
        <ReaderSettings
          anchorEl={appearanceAnchor}
          onClose={() => setAppearanceAnchor(null)}
          preferences={preferences}
          onChange={setPreferences}
          fontSizeRange={fontSizeRange}
        />
      )}

      <SelectionPopover
        rect={book.selection?.rect ?? null}
        onHighlight={workflow.highlight}
        onExtend={workflow.extend}
        onCancel={book.clearSelection}
      />
    </Box>
  );
};
