import type { NoteWithLinks } from '@/api/generated/model';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { markdownStyles } from '@/theme/theme';
import { Box, Stack, Typography, useTheme } from '@mui/material';
import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';

import { NoteKindChip } from './NoteKindChip';

interface NoteCardProps {
  note: NoteWithLinks;
  onClick: () => void;
  /**
   * Right-aligned action (e.g. an unlink button), laid over the card's top
   * corner rather than inside it: the card itself is a button, and a button
   * cannot contain another one.
   */
  action?: ReactNode;
}

export const NoteCard = ({ note, onClick, action }: NoteCardProps) => {
  const theme = useTheme();

  return (
    <Box sx={{ position: 'relative' }}>
      <HoverableCardActionArea
        onClick={onClick}
        sx={{
          // The rail is the type marker, per B9; hover is the tint and lift
          // the shared action area already carries.
          borderLeft: `3px solid ${theme.palette.primary.main}`,
          borderRadius: 0,
          display: 'block',
          textAlign: 'left',
          pl: 2,
          py: 2,
          pr: action ? 6 : 0,
        }}
      >
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
          <Typography variant="h3">{note.title}</Typography>
          <NoteKindChip kind={note.kind} />
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
      </HoverableCardActionArea>
      {action && <Box sx={{ position: 'absolute', top: 8, right: 8 }}>{action}</Box>}
    </Box>
  );
};
