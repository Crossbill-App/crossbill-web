import { ReaderIcon } from '@/theme/Icons.tsx';
import { IconButton, Tooltip, type IconButtonProps } from '@mui/material';
import { createLink } from '@tanstack/react-router';

// A link rather than a click handler, so the reader can be opened in a new tab
// and its address copied.
const ReaderLinkButton = createLink(IconButton);

export interface OpenInReaderButtonProps {
  bookId: number;
  size?: IconButtonProps['size'];
  sx?: IconButtonProps['sx'];
}

export const OpenInReaderButton = ({ bookId, size, sx }: OpenInReaderButtonProps) => (
  <Tooltip title="Open in reader">
    <ReaderLinkButton
      to="/book/$bookId/read"
      params={{ bookId: String(bookId) }}
      aria-label="Open in reader"
      size={size}
      sx={sx}
    >
      <ReaderIcon />
    </ReaderLinkButton>
  </Tooltip>
);
