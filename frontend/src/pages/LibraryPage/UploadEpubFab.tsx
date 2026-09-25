import { useCreateBookFromEpub } from '@/api/generated/books/books';
import { SNACKBAR_CLEARANCE } from '@/components/layout/Layouts.tsx';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { UploadIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, CircularProgress, Fab, Tooltip, Zoom } from '@mui/material';
import { useNavigate } from '@tanstack/react-router';
import type { AxiosError } from 'axios';
import { ChangeEvent, useRef } from 'react';

/** The server's own ceiling; checked here too so a doomed upload is never sent. */
const MAX_EPUB_BYTES = 50 * 1024 * 1024;

const REFUSALS: Record<number, string | undefined> = {
  409: 'This book is already in your library.',
  400: 'That file is not a valid EPUB.',
};

/** Picks an EPUB, adds it to the library as a new book, and opens that book. */
export const UploadEpubFab = () => {
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const cache = useCacheEvents();
  const { showSnackbar, isSnackbarOpen } = useSnackbar();
  const handleMutationError = useMutationErrorHandler();

  const { mutate: upload, isPending } = useCreateBookFromEpub<AxiosError>({
    mutation: {
      onSuccess: (book) => {
        cache.booksListChanged();
        showSnackbar(`Added "${book.title}" to your library.`, 'success');
        void navigate({ to: '/book/$bookId', params: { bookId: String(book.id) } });
      },
      onError: (error) => {
        const message = REFUSALS[error.response?.status ?? 0];
        if (message) showSnackbar(message, 'error');
        else handleMutationError('upload the book')(error);
      },
    },
  });

  const handleFileChosen = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Cleared so picking the same file again still fires a change.
    event.target.value = '';
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.epub')) {
      showSnackbar('Only EPUB files can be uploaded.', 'error');
    } else if (file.size > MAX_EPUB_BYTES) {
      showSnackbar('That file is over the 50 MB limit.', 'error');
    } else {
      upload({ data: { epub: file } });
    }
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".epub,application/epub+zip"
        hidden
        onChange={handleFileChosen}
      />
      <Zoom in={true}>
        <Box
          sx={{
            position: 'fixed',
            right: 24,
            // With no bottom nav here, the snackbar's own offset is the whole
            // clearance; on wide screens it sits centred, clear of the corner.
            bottom: { xs: isSnackbarOpen ? SNACKBAR_CLEARANCE : 24, lg: 24 },
            transition: (theme) => theme.transitions.create('bottom'),
            zIndex: (theme) => theme.zIndex.fab,
          }}
        >
          <Tooltip title="Upload EPUB">
            {/* A disabled button fires no events, so the tooltip listens on this wrapper. */}
            <span>
              <Fab
                color="primary"
                aria-label="Upload EPUB"
                disabled={isPending}
                onClick={() => inputRef.current?.click()}
              >
                {isPending ? (
                  <CircularProgress size={ICON_SIZE.prominent} color="inherit" />
                ) : (
                  <UploadIcon sx={{ fontSize: ICON_SIZE.prominent }} />
                )}
              </Fab>
            </span>
          </Tooltip>
        </Box>
      </Zoom>
    </>
  );
};
