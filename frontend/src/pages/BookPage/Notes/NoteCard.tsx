import type { NoteWithLinks } from '@/api/generated/model';
import { markdownStyles } from '@/theme/theme';
import { Box, Stack, styled, Typography, useTheme } from '@mui/material';
import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';

import { NoteKindChip } from './NoteKindChip';

interface NoteCardProps {
  note: NoteWithLinks;
  onClick: () => void;
  /**
   * Right-aligned action in the title row (e.g. an unlink button). The whole
   * card is clickable, so the action must stopPropagation on its own click.
   */
  action?: ReactNode;
}

const NoteStyled = styled(Box)(({ theme }) => ({
  borderLeft: `3px solid ${theme.palette.primary.main}`,
  paddingLeft: theme.spacing(2),
  paddingTop: theme.spacing(2),
  paddingBottom: theme.spacing(2),
  cursor: 'pointer',
  transition: 'all 0.2s ease',
  '@media (hover: hover)': {
    '&:hover': {
      backgroundColor: theme.palette.action.hover,
      boxShadow: theme.shadows[2],
    },
  },
  '&:focus-visible': {
    outline: `2px solid ${theme.palette.primary.main}`,
    outlineOffset: 2,
  },
}));

export const NoteCard = ({ note, onClick, action }: NoteCardProps) => {
  const theme = useTheme();

  return (
    <NoteStyled
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        // Ignore keys bubbling from the action button — only the card itself.
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick();
        }
      }}
    >
      <Stack
        direction="row"
        sx={{
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 0.5,
        }}
      >
        <Stack
          direction="row"
          spacing={1}
          sx={{
            alignItems: 'center',
          }}
        >
          <Typography variant="h3">{note.title}</Typography>
          <NoteKindChip kind={note.kind} />
        </Stack>
        {action}
      </Stack>
      {note.body && (
        <Box
          sx={{
            ...markdownStyles(theme),
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          <ReactMarkdown>{note.body}</ReactMarkdown>
        </Box>
      )}
    </NoteStyled>
  );
};
