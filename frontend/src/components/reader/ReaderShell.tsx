import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { useGetBookHighlightLabels } from '@/api/generated/highlight-labels/highlight-labels.ts';
import { isAnyDialogOpen } from '@/components/dialogs/dialogStack.ts';
import { manifestUrl } from '@/components/reader/api/readiumUrls.ts';
import { ExtensionBar } from '@/components/reader/chrome/ExtensionBar.tsx';
import { ReaderFooter } from '@/components/reader/chrome/ReaderFooter.tsx';
import { ReaderMessage } from '@/components/reader/chrome/ReaderMessage.tsx';
import { overlaySx } from '@/components/reader/chrome/readerOverlay.ts';
import { ReaderToolbar } from '@/components/reader/chrome/ReaderToolbar.tsx';
import { ReadingSurface } from '@/components/reader/chrome/ReadingSurface.tsx';
import { SelectionPopover } from '@/components/reader/chrome/SelectionPopover.tsx';
import { TocDrawer } from '@/components/reader/chrome/TocDrawer.tsx';
import type { EbookTocEntry } from '@/components/reader/engine/EbookReader.ts';
import {
  heldPassageDecoration,
  highlightIdFrom,
} from '@/components/reader/highlights/decorations.ts';
import { paletteFor } from '@/components/reader/highlights/highlightPalette.ts';
import { useHighlightCreation } from '@/components/reader/highlights/useHighlightCreation.ts';
import { useHighlightDecorations } from '@/components/reader/highlights/useHighlightDecorations.ts';
import { useSelectionWorkflow } from '@/components/reader/highlights/useSelectionWorkflow.ts';
import { landingOfAJump } from '@/components/reader/opening/jumpFallback.ts';
import { useEbookReader } from '@/components/reader/opening/useEbookReader.ts';
import { useLandingApology } from '@/components/reader/opening/useLandingApology.ts';
import {
  useReaderLanding,
  type ReaderTarget,
} from '@/components/reader/opening/useReaderLanding.ts';
import { useReaderSession } from '@/components/reader/opening/useReaderSession.ts';
import { useLinkHistory } from '@/components/reader/position/useLinkHistory.ts';
import { useReadingPositionWriter } from '@/components/reader/position/useReadingPositionWriter.ts';
import {
  readerPageColors,
  toEbookAppearance,
} from '@/components/reader/preferences/readerPreferences.ts';
import { ReaderSettings } from '@/components/reader/preferences/ReaderSettings.tsx';
import { useReaderPreferences } from '@/components/reader/preferences/useReaderPreferences.ts';
import { tocEntryLocation } from '@/components/reader/toc.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock.ts';
import { Box, useTheme } from '@mui/material';
import { useEffect, useMemo, useRef, useState } from 'react';

export interface ReaderShellProps {
  bookId: number;
  onClose: () => void;
  /** A highlight the reader tapped on the page. */
  onOpenHighlight?: (highlightId: number) => void;
  /** Where to open the book; only its value at mount counts. */
  target?: ReaderTarget | null;
}

/** Said over the open book for a tap that landed in a chapter the passage cannot reach. */
const ONE_CHAPTER_ONLY = 'A highlight has to stay inside one chapter.';

/** The reader's full-viewport frame: a title bar, a way out, and the book. */
export const ReaderShell = ({ bookId, onClose, onOpenHighlight, target }: ReaderShellProps) => {
  // A fixed overlay never scrolls the body, which is what arms pull-to-refresh.
  useBodyScrollLock(true);
  const { status: sessionStatus, isRenewing } = useReaderSession(bookId);
  const { data: details } = useGetBookDetails(bookId);
  const title = details?.title ?? '';
  // A new array every render would be a new set of decorations every render.
  const highlights = useMemo(
    () => details?.chapters.flatMap((chapter) => chapter.highlights),
    [details]
  );
  const { data: labels } = useGetBookHighlightLabels(bookId);
  const palette = paletteFor(labels?.items ?? []);
  const host = useRef<HTMLDivElement | null>(null);
  const [isTocOpen, setIsTocOpen] = useState(false);
  const [preferences, setPreferences] = useReaderPreferences();
  // Never undefined: the palette is the nine colours, and a stored colour
  // outside them is read back as the default.
  const selectedColor =
    palette.find((color) => color.device_color === preferences.highlightColor) ?? palette[0];
  const [appearanceAnchor, setAppearanceAnchor] = useState<Element | null>(null);
  const theme = useTheme();
  const pageColors = readerPageColors(theme, preferences.pageColor);
  // A new object submits the same appearance to the engine again, which reflows
  // the book rather than costing nothing. Keyed on the fields an appearance is
  // made of, so the highlight colour stored beside them buys no reflow.
  const { pageColor, fontSize, spacing, alignment, columns } = preferences;
  const appearance = useMemo(
    () => toEbookAppearance(theme, { pageColor, fontSize, spacing, alignment, columns }),
    [theme, pageColor, fontSize, spacing, alignment, columns]
  );
  const { seed, moved } = useReadingPositionWriter(bookId);
  const linkHistory = useLinkHistory(bookId);
  // Latched, so that nothing done to the address after the book opens can move it.
  const [jump] = useState(target ?? null);
  const landing = useReaderLanding(bookId, jump, details?.chapters);
  const placedHighlights = useHighlightDecorations(bookId, highlights);
  const creation = useHighlightCreation(bookId);
  const { showSnackbar } = useSnackbar();
  const book = useEbookReader({
    host,
    manifestUrl: manifestUrl(bookId),
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
    on: {
      arrivedAt: (location) => {
        seed(location);
        linkHistory.record(location);
      },
      movedTo: (location) => {
        moved(location);
        linkHistory.record(location);
      },
      linkFollowed: linkHistory.linkFollowed,
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
      jump === null
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

  const { onReturn } = linkHistory;
  const { goTo } = book;
  useEffect(() => onReturn(goTo), [onReturn, goTo]);

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

  useLandingApology(book, landing, jump);

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

      <ReaderFooter
        progression={book.location?.locations.totalProgression}
        chapterProgress={book.chapterProgress}
        colors={pageColors}
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
        palette={palette}
        selected={selectedColor}
        onSelect={(color) => setPreferences({ ...preferences, highlightColor: color.device_color })}
        onHighlight={() => workflow.highlight(selectedColor)}
        onExtend={workflow.extend}
        onCancel={book.clearSelection}
      />
    </Box>
  );
};
