import { useDeleteBook, useUpdateBook } from '@/api/generated/books/books.ts';
import { BookDetails } from '@/api/generated/model';
import { BookCover } from '@/components/BookCover.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { DeleteIcon } from '@/theme/Icons.tsx';
import { Box, Button, Typography } from '@mui/material';
import { useNavigate } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';

interface BookEditDialogProps {
  book: BookDetails;
  open: boolean;
  onClose: () => void;
}

export const BookEditDialog = ({ book, open, onClose }: BookEditDialogProps) => {
  const cache = useCacheEvents();
  const navigate = useNavigate();
  const mutationErrorHandler = useMutationErrorHandler();
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const deleteBookMutation = useDeleteBook({
    mutation: {
      onSuccess: () => {
        cache.booksListChanged();
        onClose();
        navigate({ to: '/' });
      },
      onError: mutationErrorHandler('delete book'),
    },
  });

  const handleDelete = () => {
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = () => {
    setDeleteConfirmOpen(false);
    deleteBookMutation.mutate({ bookId: book.id });
  };

  const isDeleting = deleteBookMutation.isPending;

  const {
    control,
    handleSubmit,
    reset,
    formState: { isDirty },
  } = useForm<{ description: string }>({
    defaultValues: { description: book.description ?? '' },
  });

  // Re-seed whenever the dialog (re)opens or a refetch brings a newer blurb,
  // so a closed dialog's abandoned draft never survives to the next open —
  // discarding it on close is what keeps the dialog and header consistent.
  useEffect(() => {
    if (open) reset({ description: book.description ?? '' });
  }, [open, book.description, reset]);

  const updateBookMutation = useUpdateBook({
    mutation: {
      onSuccess: () => {
        cache.bookChanged(book.id);
        onClose();
      },
      onError: mutationErrorHandler('save blurb'),
    },
  });

  const onSubmit = ({ description }: { description: string }) =>
    updateBookMutation.mutate({
      bookId: book.id,
      data: { description: description.trim() || null },
    });

  const isSaving = updateBookMutation.isPending;

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      isLoading={isDeleting || isSaving}
      title="Manage Book"
      footerActions={
        <Box sx={{ display: 'flex', gap: 1, width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose} disabled={isSaving || isDeleting}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit(onSubmit)}
            variant="contained"
            disabled={!isDirty || isSaving || isDeleting}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </Button>
        </Box>
      }
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
        }}
      >
        {/* Book Info Display */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            alignItems: { xs: 'center', sm: 'flex-start' },
            mt: 3,
          }}
        >
          <BookCover
            coverFile={book.cover_file ?? null}
            title={book.title}
            blurhash={book.cover_blurhash}
            width="120px"
            height="180px"
            objectFit="cover"
            sx={{ borderRadius: 1 }}
          />
          <Box
            sx={{
              flex: 1,
              textAlign: { xs: 'center', sm: 'left' },
              width: { xs: '100%', sm: 'auto' },
            }}
          >
            <Typography variant="h6" gutterBottom>
              {book.title}
            </Typography>
            <Typography
              variant="body2"
              gutterBottom
              sx={{
                color: 'text.secondary',
              }}
            >
              {book.author || 'Unknown Author'}
            </Typography>
            {book.isbn && (
              <Typography
                variant="body2"
                gutterBottom
                sx={{
                  color: 'text.secondary',
                }}
              >
                ISBN: {book.isbn}
              </Typography>
            )}
            <Button
              onClick={handleDelete}
              color="error"
              size="small"
              startIcon={<DeleteIcon />}
              disabled={isDeleting || isSaving}
              sx={{ mt: 1 }}
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </Box>
        </Box>

        <RHFTextField
          name="description"
          control={control}
          label="Blurb"
          multiline
          minRows={4}
          fullWidth
          disabled={isSaving}
          slotProps={{ htmlInput: { maxLength: 5000 } }}
          helperText="Markdown is supported. Shown under the book's title."
        />
      </Box>

      <ConfirmationDialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Book"
        message={`Are you sure you want to delete "${book.title}"? This will permanently delete the book and all its highlights.`}
        confirmText="Delete"
        confirmColor="error"
        isLoading={isDeleting}
      />
    </CommonDialog>
  );
};
