import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import { QueryClientProvider } from '@tanstack/react-query';
import ReactDOM from 'react-dom/client';
import App from './App';
import { SnackbarProvider } from './context/SnackbarContext';
import { queryClient } from './lib/queryClient';
import { theme } from './theme/theme';

// SPIKE #740 — React.StrictMode is DISABLED on this branch, and must be put
// back before anything here is merged.
//
// It is off because thorium-web 1.6.0 keeps its EpubNavigator in a module-level
// singleton (`var navigatorInstance2 = null` in dist/chunk-CXKDZVAV.mjs) and
// `EpubNavigatorDestroy` nulls it in a `.then()`. StrictMode's double-mount
// runs load -> destroy -> load, and the first destroy's promise resolves after
// the second load has already assigned, so the singleton ends up null while the
// reader is still on screen. Every accessor `useEpubNavigator()` hands out —
// `currentLocator()`, `getCframes()`, `goLink()` — then silently no-ops.
// Measured: with StrictMode on, `getCframes()` returns [] while 4 iframes are
// rendered and the book is legible. The bare-navigator route (spike.bare.tsx)
// has no such problem; it owns its instance in a ref.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <SnackbarProvider>
          <App />
        </SnackbarProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </>
);
