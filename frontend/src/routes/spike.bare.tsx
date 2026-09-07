/* eslint-disable react-refresh/only-export-components */
/**
 * SPIKE #740 — throwaway. The alternative to thorium-web: bare
 * `@readium/navigator`, our own chrome, our own listeners.
 *
 * The point of this file is the contrast with spike.reader.tsx. Here
 * `frameLoaded` and `textSelected` are OURS, and `applyDecorations` is called
 * directly on the navigator instance we own — no singleton, no Redux, no
 * i18next, no react-aria.
 *
 * Usage: /spike/bare?bookId=12
 */
import { getAccessToken } from '@/api/token-manager';
import { Box, Button, Stack, Typography } from '@mui/material';
import { DecorationStyleType, EpubNavigator } from '@readium/navigator';
import { HttpFetcher, Link, Locator, LocatorText, Manifest, Publication } from '@readium/shared';
import { createFileRoute } from '@tanstack/react-router';
import { useCallback, useEffect, useRef, useState } from 'react';

export const Route = createFileRoute('/spike/bare')({
  component: BareReaderRoute,
  validateSearch: (search: Record<string, unknown>) => ({
    bookId: Number(search.bookId ?? 12),
  }),
});

function BareReaderRoute() {
  const { bookId } = Route.useSearch();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const navRef = useRef<EpubNavigator | null>(null);
  const [status, setStatus] = useState('starting');
  const [selection, setSelection] = useState<string | null>(null);
  const [frameLoads, setFrameLoads] = useState(0);

  useEffect(() => {
    let destroyed = false;

    const boot = async () => {
      const token = getAccessToken() ?? sessionStorage.getItem('spikeToken');
      const base = `/api/v1/readium/books/${bookId}`;

      setStatus('minting publication cookie');
      const session = await fetch(`${base}/session`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'same-origin',
      });
      if (!session.ok) throw new Error(`session ${session.status}`);

      setStatus('fetching manifest');
      const selfHref = `${window.location.origin}${base}/manifest.json`;
      const fetcher = new HttpFetcher(undefined, selfHref);
      const manifestData = await fetcher.get(new Link({ href: selfHref })).readAsJSON();
      const manifest = Manifest.deserialize(manifestData);
      if (!manifest) throw new Error('manifest did not deserialize');
      manifest.setSelfLink(selfHref);
      const publication = new Publication({ manifest, fetcher });

      setStatus('fetching positions');
      const positions = await publication.positionsFromManifest();

      if (destroyed || !containerRef.current) return;
      setStatus('loading navigator');

      // Every listener is ours. This is the whole difference from thorium.
      const navigator = new EpubNavigator(
        containerRef.current,
        publication,
        {
          frameLoaded: () => setFrameLoads((n) => n + 1),
          positionChanged: () => {},
          timelineItemChanged: () => {},
          tap: () => true,
          click: () => true,
          zoom: () => {},
          miscPointer: () => {},
          scroll: () => {},
          customEvent: () => {},
          handleLocator: () => false,
          // `sel.locator` is populated by the navigator — this is the
          // browser-selection -> Locator -> XPointRange write path of ADR-0004 §2.
          textSelected: (sel) => setSelection(`${sel.text} @ ${sel.locator?.href ?? '?'}`),
          contentProtection: () => {},
          contextMenu: () => {},
          peripheral: () => {},
        },
        positions
      );
      navRef.current = navigator;
      await navigator.load();
      if (!destroyed) setStatus('ready');
    };

    boot().catch((e) => setStatus(`error: ${e}`));
    return () => {
      destroyed = true;
      navRef.current?.destroy();
      navRef.current = null;
    };
  }, [bookId]);

  /** Our highlight layer, calling the navigator's own public decoration API. */
  const highlightFirstParagraph = useCallback(() => {
    const navigator = navRef.current;
    if (!navigator) return;
    const frame = navigator._cframes.find(Boolean);
    const phrase = frame?.window.document
      .querySelector('p')
      ?.textContent?.trim()
      .split(/\s+/)
      .slice(0, 8)
      .join(' ');
    if (!phrase) return;
    navigator.applyDecorations(
      [
        {
          id: 'bare-1',
          locator: new Locator({
            href: navigator.currentLocator.href,
            type: 'application/xhtml+xml',
            text: new LocatorText({ highlight: phrase }),
          }),
          style: { type: DecorationStyleType.Highlight, tint: '#4dd0e1' },
        },
      ],
      'crossbill-highlights'
    );
  }, []);

  return (
    <Box sx={{ position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <Stack direction="row" spacing={2} sx={{ p: 1, alignItems: 'center' }}>
        <Typography variant="body2">
          {status} | frameLoaded x{frameLoads} | selection: {selection ?? 'none'}
        </Typography>
        <Button size="small" onClick={() => navRef.current?.goForward(true, () => {})}>
          Next
        </Button>
        <Button size="small" onClick={highlightFirstParagraph}>
          Highlight
        </Button>
      </Stack>
      <Box ref={containerRef} data-testid="bare-reader" sx={{ flex: 1, minHeight: 0 }} />
    </Box>
  );
}
