import type { NoteWithLinks } from '@/api/generated/model';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { TagChipList } from '@/components/TagChipList.tsx';
import { DateIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { markdownStyles } from '@/theme/theme';
import { formatDate } from '@/utils/date.ts';
import { Box, Typography, useTheme } from '@mui/material';
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
          display: 'block',
          textAlign: 'left',
          pl: 2.5,
          py: 1,
          pr: action ? 6 : 2.5,
        }}
      >
        <Typography variant="h3" sx={{ mb: 0.5 }}>
          {note.title}
        </Typography>
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
        {/* After the content, as on the highlight card: the footer marks where one card ends. */}
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 2, mt: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
            <DateIcon sx={{ fontSize: ICON_SIZE.inline, color: 'text.secondary' }} />
            <MetadataRow variant="caption" items={[formatDate(note.created_at)]} />
            <NoteKindChip kind={note.kind} />
          </Box>
          <TagChipList tags={note.tags} />
        </Box>
      </HoverableCardActionArea>
      {action && <Box sx={{ position: 'absolute', top: 8, right: 8 }}>{action}</Box>}
    </Box>
  );
};
