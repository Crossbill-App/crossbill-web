import { API_BASE_URL } from '@/api/base-url';
import { BookCoverIcon } from '@/theme/Icons.tsx';
import { Box, type SxProps, type Theme, useTheme } from '@mui/material';
import { useState } from 'react';
import { Blurhash } from 'react-blurhash';

/** Neutral gray fallback for books without a generated blurhash. */
const FALLBACK_BLURHASH = 'L6PZfSi_.AyE_3t7t7R**0o#DgR4';

export interface BookCoverProps {
  coverFile: string | null;
  title: string;
  /**
   * Blurhash string for placeholder. Falls back to a neutral default if null.
   */
  blurhash?: string | null;
  width?: number | string | { xs?: number | string; sm?: number | string };
  height?: number | string | { xs?: number | string; sm?: number | string };
  objectFit?: 'contain' | 'cover';
  sx?: SxProps<Theme>;
}

export const BookCover = ({
  coverFile,
  title,
  blurhash,
  width = '100%',
  height = 200,
  objectFit = 'contain',
  sx,
}: BookCoverProps) => {
  const theme = useTheme();

  const coverUrl = coverFile ? `${API_BASE_URL}/api/v1/covers/${coverFile}` : null;
  const [imageLoaded, setImageLoaded] = useState(false);

  const numericHeight = typeof height === 'number' ? height : 200;

  return (
    <Box
      className="book-cover"
      sx={{
        width,
        height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        position: 'relative',
        ...sx,
      }}
    >
      {coverUrl ? (
        <>
          {/* Blurhash placeholder — visible until image loads */}
          {!imageLoaded && (
            <Box
              sx={{
                position: 'absolute',
                inset: 0,
              }}
            >
              <Blurhash hash={blurhash || FALLBACK_BLURHASH} width="100%" height="100%" />
            </Box>
          )}

          {/* Actual cover image */}
          <img
            src={coverUrl}
            alt={`${title} cover`}
            style={{
              width: '100%',
              height: '100%',
              objectFit,
              opacity: imageLoaded ? 1 : 0,
              transition: 'opacity 0.3s ease-in',
            }}
            onLoad={() => setImageLoaded(true)}
            onError={(e) => {
              e.currentTarget.style.display = 'none';
              const placeholder = e.currentTarget.parentElement!.querySelector(
                '.book-cover-icon-fallback'
              ) as HTMLElement | null;
              if (placeholder) placeholder.style.display = 'flex';
            }}
          />

          {/* Icon fallback for broken images */}
          <Box
            className="book-cover-icon-fallback"
            sx={{
              display: 'none',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              height: '100%',
              background: theme.palette.action.hover,
            }}
          >
            <BookCoverIcon
              sx={{
                fontSize: numericHeight * 0.4,
                color: 'text.disabled',
                opacity: 1,
              }}
            />
          </Box>
        </>
      ) : (
        /* No cover file at all — show icon placeholder */
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            background: theme.palette.action.hover,
          }}
        >
          <BookCoverIcon
            sx={{
              fontSize: numericHeight * 0.4,
              color: 'text.disabled',
              opacity: 1,
            }}
          />
        </Box>
      )}
    </Box>
  );
};
