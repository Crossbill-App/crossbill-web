import type { NoteWithLinks } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { List, ListItemButton, ListItemText, Typography } from '@mui/material';

interface NotePickerDialogProps {
  open: boolean;
  onClose: () => void;
  bookId: number;
  title: string;
  onSelect: (note: NoteWithLinks) => void;
}

export const NotePickerDialog = ({
  open,
  onClose,
  bookId,
  title,
  onSelect,
}: NotePickerDialogProps) => {
  const { data, isLoading } = useGetNotesForBook(bookId, undefined, {
    query: { enabled: open },
  });

  // NOTE: the orval axios mutator unwraps the response (`.then(({ data }) => data)`),
  // so the generated GET hook's `data` is the payload itself, not an AxiosResponse.
  const notes = data?.items ?? [];

  return (
    <CommonDialog open={open} onClose={onClose} title={title} maxWidth="sm">
      {isLoading && <Spinner />}
      {!isLoading && notes.length === 0 && (
        <Typography color="text.secondary">No notes in this book yet.</Typography>
      )}
      <List>
        {notes.map((note) => (
          <ListItemButton key={note.id} onClick={() => onSelect(note)}>
            <ListItemText primary={note.title} secondary={note.kind ?? undefined} />
          </ListItemButton>
        ))}
      </List>
    </CommonDialog>
  );
};
