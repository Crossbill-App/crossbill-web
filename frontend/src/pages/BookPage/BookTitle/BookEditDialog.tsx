import { useDeleteBook } from '@/api/generated/books/books.ts';
import { BookDetails } from '@/api/generated/model';
import { BookCover } from '@/components/BookCover.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { DeleteIcon } from '@/theme/Icons.tsx';
import { Box, Button, Typography } from '@mui/material';
import { useNavigate } from '@tanstack/react-router';
import { useState } from 'react';

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

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      isLoading={isDeleting}
      title="Manage Book"
      footerActions={
        <>
          <Button
            onClick={handleDelete}
            color="error"
            startIcon={<DeleteIcon />}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </Button>
          <Button onClick={onClose} disabled={isDeleting}>
            Close
          </Button>
        </>
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
          </Box>
        </Box>
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
