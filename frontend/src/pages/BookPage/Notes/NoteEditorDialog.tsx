import type { Note } from '@/api/generated/model';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { Box, Button } from '@mui/material';
import { useRef, useState } from 'react';

import { NoteEditorForm, type NoteEditorFormHandle, type NoteGuidance } from './NoteEditorForm';
import type { NoteKindValue } from './noteKinds';

interface NoteEditorDialogProps {
  open: boolean;
  onClose: () => void;
  initialChapterIds?: number[];
  initialHighlightIds?: number[];
  initialBody?: string;
  initialKind?: NoteKindValue;
  initialTitle?: string;
  /** Always-visible prompt shown above the form (e.g. a reflection question). */
  guidance?: NoteGuidance;
  /** Called with the created note after a successful create (not on update). */
  onCreated?: (note: Note) => void;
}

/**
 * Creating a note. Editing an existing one belongs to `NoteViewDialog`, which
 * keeps the note itself on screen around the form.
 */
export const NoteEditorDialog = ({
  open,
  onClose,
  initialChapterIds,
  initialHighlightIds,
  initialBody,
  initialKind,
  initialTitle,
  guidance,
  onCreated,
}: NoteEditorDialogProps) => {
  const formRef = useRef<NoteEditorFormHandle>(null);
  const [status, setStatus] = useState({ isSaving: false, canSave: false });

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      title="New note"
      maxWidth="md"
      isLoading={status.isSaving}
      footerActions={
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button onClick={onClose} disabled={status.isSaving}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => formRef.current?.submit()}
            disabled={!status.canSave}
          >
            {status.isSaving ? 'Saving...' : 'Save'}
          </Button>
        </Box>
      }
    >
      <NoteEditorForm
        ref={formRef}
        open={open}
        initialChapterIds={initialChapterIds}
        initialHighlightIds={initialHighlightIds}
        initialBody={initialBody}
        initialKind={initialKind}
        initialTitle={initialTitle}
        guidance={guidance}
        onCreated={onCreated}
        onSaved={onClose}
        onStatusChange={setStatus}
      />
    </CommonDialog>
  );
};
