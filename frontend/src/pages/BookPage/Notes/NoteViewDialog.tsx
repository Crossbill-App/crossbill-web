import type { Highlight } from '@/api/generated/model';
import { useDeleteNote, useGetNote } from '@/api/generated/notes/notes.ts';
import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { CommonDialogTitle } from '@/components/dialogs/CommonDialogTitle.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { ProgressBar } from '@/components/dialogs/ProgressBar.tsx';
import { useDialogHorizontalNavigation } from '@/components/dialogs/useDialogHorizontalNavigation.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { markdownStyles } from '@/theme/theme';
import { copyUrlWithSearchParam } from '@/utils/clipboard.ts';
import { Box, Button, Chip, Stack, Typography, useTheme } from '@mui/material';
import { useNavigate } from '@tanstack/react-router';
import { useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';

import { NoteTabs } from './components/NoteTabs';
import { NoteToolbar } from './components/NoteToolbar';
import { useNoteLinks } from './hooks/useNoteLinks';
import { NoteEditorForm, type NoteEditorFormHandle, type NoteGuidance } from './NoteEditorForm';
import { NoteKindChip } from './NoteKindChip';

interface NoteViewDialogProps {
  /** Note to display; its full detail (with linked summaries) is fetched by id. */
  noteId: number;
  onClose: () => void;
  /** Position of the note in the parent's ordered list; enables prev/next navigation. */
  currentIndex?: number;
  totalCount?: number;
  onNavigate?: (newIndex: number) => void;
  /** Opens straight into the in-place editor, for entry points that mean "edit this". */
  initiallyEditing?: boolean;
  /** Always-visible prompt shown above the editor (e.g. a reflection question). */
  guidance?: NoteGuidance;
}

/**
 * Read-only note detail dialog that toggles into an in-place editor. Read mode
 * shows the full note (content first) with an action toolbar underneath;
 * clicking Edit swaps the same dialog to the note editor form. This is the one
 * surface for editing an existing note — entry points that mean "edit this"
 * open it with `initiallyEditing`, so the note's context is never lost behind a
 * second modal.
 *
 * Opened by note id (deep-linkable via the `noteId` URL param). Stays mounted
 * across prev/next navigation (mirroring the highlight dialog), so transient
 * state is reset explicitly when the viewed note changes.
 */
export const NoteViewDialog = ({
  noteId,
  onClose,
  currentIndex,
  totalCount,
  onNavigate,
  initiallyEditing = false,
  guidance,
}: NoteViewDialogProps) => {
  const theme = useTheme();
  const { book } = useBookPage();
  const { showSnackbar } = useSnackbar();
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const navigate = useNavigate();

  // Navigating to another route drops the `noteId` param, so the note dialog
  // closes naturally as the target entity's deep link opens its dialog there.
  const handleOpenHighlight = (highlightId: number) => {
    void navigate({
      to: '/book/$bookId/highlights',
      params: { bookId: String(book.id) },
      search: { highlightId },
    });
  };

  const handleOpenChapter = (chapterId: number) => {
    void navigate({
      to: '/book/$bookId/structure',
      params: { bookId: String(book.id) },
      search: { chapterId },
    });
  };

  const [isEditing, setIsEditing] = useState(initiallyEditing);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const formRef = useRef<NoteEditorFormHandle>(null);
  const [formStatus, setFormStatus] = useState({ isSaving: false, canSave: false });

  // The dialog stays mounted while navigating between notes, so transient
  // state must be reset explicitly when the viewed note changes.
  const [prevNoteId, setPrevNoteId] = useState(noteId);
  if (prevNoteId !== noteId) {
    setPrevNoteId(noteId);
    setIsEditing(initiallyEditing);
    setDeleteConfirmOpen(false);
  }

  const { navigation } = useDialogHorizontalNavigation({
    currentIndex: currentIndex ?? 0,
    totalCount: totalCount ?? 1,
    // Suspend navigation while editing so arrows/swipes can't discard edits.
    onNavigate: isEditing ? undefined : onNavigate,
  });

  const { data: activeNote, isLoading, isError } = useGetNote(noteId);

  const deleteMutation = useDeleteNote({
    mutation: {
      onSuccess: () => {
        cache.noteDeleted(book.id, noteId);
        setDeleteConfirmOpen(false);
        onClose();
      },
      onError: mutationErrorHandler('delete note'),
    },
  });

  const handleCopy = async () => {
    if (!activeNote) return;
    await navigator.clipboard.writeText(activeNote.body);
    showSnackbar('Note copied to clipboard.', 'success');
  };

  // Copy a link that works from any context: `noteId` is only a validated
  // search param on the notes route, so build the URL on that route.
  const handleCopyLink = async () => {
    await copyUrlWithSearchParam(
      'noteId',
      noteId,
      `${window.location.origin}/book/${book.id}/notes`
    );
  };

  const handleConfirmDelete = () => {
    void deleteMutation.mutateAsync({ noteId });
  };

  const noteLinks = useNoteLinks({ bookId: book.id });

  const isDeleting = deleteMutation.isPending;

  const chapters = activeNote?.chapters ?? [];
  const tags = activeNote?.tags ?? [];
  // The note detail returns lightweight highlight summaries; resolve them to the
  // full Highlight objects already loaded on the book so we can render HighlightCard.
  const highlights = useMemo<Highlight[]>(() => {
    if (!activeNote?.highlights?.length) return [];
    const byId = new Map<number, Highlight>();
    for (const chapter of book.chapters) {
      for (const highlight of chapter.highlights) {
        byId.set(highlight.id, highlight);
      }
    }
    return activeNote.highlights
      .map((summary) => byId.get(summary.id))
      .filter((highlight): highlight is Highlight => highlight !== undefined);
  }, [book.chapters, activeNote]);

  // Only while editing: viewing has nothing to confirm, and the header's close
  // button is the way out.
  const footerActions = isEditing ? (
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Button onClick={() => setIsEditing(false)} disabled={formStatus.isSaving}>
        Cancel
      </Button>
      <Button
        variant="contained"
        onClick={() => formRef.current?.submit()}
        disabled={!formStatus.canSave}
      >
        {formStatus.isSaving ? 'Saving...' : 'Save'}
      </Button>
    </Box>
  ) : undefined;

  return (
    <CommonDialog
      open
      onClose={onClose}
      maxWidth="md"
      isLoading={isEditing ? formStatus.isSaving : isDeleting}
      headerElement={
        currentIndex !== undefined && totalCount !== undefined ? (
          <ProgressBar currentIndex={currentIndex} totalCount={totalCount} />
        ) : undefined
      }
      title={
        <CommonDialogTitle>
          {isEditing ? 'Edit note' : (activeNote?.title ?? 'Note')}
          <NoteKindChip kind={activeNote?.kind} sx={{ mb: 0.5, ml: 1 }} />
        </CommonDialogTitle>
      }
      footerActions={footerActions}
      navigation={navigation}
    >
      <Box
        sx={{
          mt: 2,
          mb: 2,
        }}
      >
        {isEditing && activeNote ? (
          <NoteEditorForm
            ref={formRef}
            open={isEditing}
            note={activeNote}
            guidance={guidance}
            onSaved={() => setIsEditing(false)}
            onStatusChange={setFormStatus}
          />
        ) : activeNote ? (
          <FadeInOut ekey={noteId}>
            <Stack
              sx={{
                gap: 2,
              }}
            >
              <Box>
                {activeNote.body && (
                  <Box sx={markdownStyles(theme)}>
                    <ReactMarkdown>{activeNote.body}</ReactMarkdown>
                  </Box>
                )}
                {tags.length > 0 && (
                  <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: 'wrap', gap: 0.5 }}>
                    {tags.map((tag) => (
                      <Chip
                        key={`tag-${tag.id}`}
                        size="small"
                        variant="outlined"
                        label={`#${tag.name}`}
                      />
                    ))}
                  </Stack>
                )}
              </Box>
              <NoteToolbar
                onCopyLink={() => void handleCopyLink()}
                onEdit={() => setIsEditing(true)}
                onCopy={() => void handleCopy()}
                onDelete={() => setDeleteConfirmOpen(true)}
                disabled={isDeleting}
              />
              <NoteTabs
                note={activeNote}
                bookId={book.id}
                highlights={highlights}
                chapters={chapters}
                onOpenHighlight={handleOpenHighlight}
                onOpenChapter={handleOpenChapter}
                onUnlinkHighlight={(highlightId) =>
                  noteLinks.unlinkHighlight(activeNote, highlightId)
                }
                onUnlinkChapter={(chapterId) => noteLinks.unlinkChapter(activeNote, chapterId)}
                disabled={isDeleting || noteLinks.isPending}
              />
            </Stack>
          </FadeInOut>
        ) : isError ? (
          <Typography
            sx={{
              color: 'text.secondary',
            }}
          >
            This note could not be found. It may have been deleted.
          </Typography>
        ) : (
          isLoading && <Spinner />
        )}
      </Box>

      <ConfirmationDialog
        open={deleteConfirmOpen}
        title="Delete note"
        message={`Delete note "${activeNote?.title ?? ''}"? This cannot be undone.`}
        confirmText="Delete"
        confirmColor="error"
        onConfirm={handleConfirmDelete}
        onClose={() => setDeleteConfirmOpen(false)}
        isLoading={isDeleting}
      />
    </CommonDialog>
  );
};
