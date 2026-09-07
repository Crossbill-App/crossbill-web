/* eslint-disable react-refresh/only-export-components */
/**
 * SPIKE #740 — throwaway. Renders @edrlab/thorium-web's StatefulReader against
 * the M1 backend surface to find out what breaks. Not for merge.
 *
 * Usage: /spike/reader?bookId=12
 *
 * Provider stack, learned the hard way (each one is a runtime throw if absent):
 *   ThStoreProvider                    — thorium's own Redux store
 *   StatefulGlobalPreferencesProvider  — reads that store; ThI18nProvider needs it
 *   StatefulReaderWrapper              — supplies ThI18nProvider + ThPreferencesProvider itself
 */
import { getAccessToken } from '@/api/token-manager';
import { useEpubNavigator } from '@edrlab/thorium-web/core/hooks';
import { ThStoreProvider } from '@edrlab/thorium-web/core/lib';
import '@edrlab/thorium-web/epub/styles';
import {
  StatefulGlobalPreferencesProvider,
  StatefulReaderWrapper,
  usePublication,
} from '@edrlab/thorium-web/reader';
import '@edrlab/thorium-web/reader/styles';
import { Box, Typography } from '@mui/material';
import { DecorationStyleType, resolveDecorationForWire } from '@readium/navigator';
import { Locator, LocatorLocations, LocatorText } from '@readium/shared';
import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';

export const Route = createFileRoute('/spike/reader')({
  component: SpikeReaderRoute,
  validateSearch: (search: Record<string, unknown>) => ({
    bookId: Number(search.bookId ?? 12),
    // SPIKE: lets the route be opened from a pasted URL without a login.
    token: typeof search.token === 'string' ? search.token : undefined,
  }),
});

/** Mints the publication cookie (ADR-0004 Amendment 1) before the navigator loads anything. */
function usePublicationSession(bookId: number) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // SPIKE: sessionStorage fallback so the route can be driven without a login.
    const token =
      getAccessToken() ??
      new URLSearchParams(window.location.search).get('token') ??
      sessionStorage.getItem('spikeToken');
    fetch(`/api/v1/readium/books/${bookId}/session`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'same-origin',
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`session ${r.status}: ${await r.text()}`);
        return r.json();
      })
      .then((body) => {
        if (!cancelled) {
          console.info('[spike] publication session', body);
          setReady(true);
        }
      })
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  return { ready, error };
}

function ReaderInner({ bookId }: { bookId: number }) {
  const manifestUrl = `${window.location.origin}/api/v1/readium/books/${bookId}/manifest.json`;
  const pub = usePublication({
    url: manifestUrl,
    onError: (e) => console.error('[spike] usePublication error', e),
  });

  useEffect(() => {
    (window as unknown as Record<string, unknown>).__spike = pub;
    console.info('[spike] usePublication', {
      isLoading: pub.isLoading,
      error: pub.error,
      profile: pub.profile,
      selfLink: pub.selfLink,
      hasPublication: !!pub.publication,
    });
  }, [pub]);

  if (pub.error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">usePublication error: {JSON.stringify(pub.error)}</Typography>
      </Box>
    );
  }
  if (pub.isLoading || !pub.publication || !pub.profile) {
    return <Box sx={{ p: 3 }}>Loading publication...</Box>;
  }

  return (
    <Box data-testid="spike-reader-host" sx={{ position: 'fixed', inset: 0 }}>
      <StatefulReaderWrapper
        profile={pub.profile}
        publication={pub.publication}
        localDataKey={pub.localDataKey}
        isLoading={pub.isLoading}
      />
      <SeamProbe />
    </Box>
  );
}

/**
 * The load-bearing question of #740: is there a seam from a thorium child
 * component to the highlight layer? Renders nothing; parks handles on `window`
 * so the Playwright driver can interrogate them.
 */
function SeamProbe() {
  const nav = useEpubNavigator();
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__seam = {
      nav,
      keys: Object.keys(nav),
      // Public @readium/navigator exports our decoration layer would need.
      resolveDecorationForWire,
      DecorationStyleType,
      Locator,
      LocatorLocations,
      LocatorText,
    };
  }, [nav]);
  return null;
}

function SpikeReaderRoute() {
  const { bookId } = Route.useSearch();
  const { ready, error } = usePublicationSession(bookId);

  if (error) return <Box sx={{ p: 3 }}>session error: {error}</Box>;
  if (!ready) return <Box sx={{ p: 3 }}>Minting publication cookie...</Box>;

  return (
    <ThStoreProvider storageKey="spike-740">
      <StatefulGlobalPreferencesProvider>
        <ReaderInner bookId={bookId} />
      </StatefulGlobalPreferencesProvider>
    </ThStoreProvider>
  );
}
