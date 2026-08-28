import type { NoteWithLinks } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { NoteKindChip } from '@/pages/BookPage/Notes/NoteKindChip.tsx';
import { Box, List, ListItemButton, ListItemText, Typography } from '@mui/material';

/** What the picked note gets linked to, named in the dialog's subtitle. */
type NoteLinkTargetKind = 'highlight' | 'chapter' | 'reflection';

interface NotePickerDialogProps {
  open: boolean;
  onClose: () => void;
  bookId: number;
  target: NoteLinkTargetKind;
  onSelect: (note: NoteWithLinks) => void;
}

export const NotePickerDialog = ({
  open,
  onClose,
  bookId,
  target,
  onSelect,
}: NotePickerDialogProps) => {
  const { data, isLoading } = useGetNotesForBook(bookId, undefined, {
    query: { enabled: open },
  });

  // NOTE: the orval axios mutator unwraps the response (`.then(({ data }) => data)`),
  // so the generated GET hook's `data` is the payload itself, not an AxiosResponse.
  const notes = data?.items ?? [];

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      title={
        <Box>
          Link a note
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {`Choose a note to link to this ${target}.`}
          </Typography>
        </Box>
      }
      maxWidth="sm"
    >
      {isLoading && <Spinner />}
      {!isLoading && notes.length === 0 && (
        <EmptyStateText>No notes in this book yet.</EmptyStateText>
      )}
      <List>
        {notes.map((note) => (
          <ListItemButton key={note.id} onClick={() => onSelect(note)}>
            <ListItemText primary={note.title} />
            <NoteKindChip kind={note.kind} />
          </ListItemButton>
        ))}
      </List>
    </CommonDialog>
  );
};
