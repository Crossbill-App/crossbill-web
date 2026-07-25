import { useDeleteBook } from '@/api/generated/books/books.ts';
import { BookDetails } from '@/api/generated/model';
import { BookCover } from '@/components/BookCover.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { useBookMutationHelpers } from '@/hooks/useBookMutationHelpers.ts';
import { DeleteIcon } from '@/theme/Icons.tsx';
import { Box, Button, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import { useState } from 'react';

interface BookEditModalProps {
  book: BookDetails;
  open: boolean;
  onClose: () => void;
}

export const BookEditModal = ({ book, open, onClose }: BookEditModalProps) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { mutationErrorHandler } = useBookMutationHelpers(book.id);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const deleteBookMutation = useDeleteBook({
    mutation: {
      onSuccess: async () => {
        // Refetch the books list query and wait for it to complete
        await queryClient.refetchQueries({
          queryKey: ['/api/v1/books'],
          exact: true,
        });
        // Close modal and navigate to landing page after refetch is complete
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
      <Box display="flex" flexDirection="column" gap={3}>
        {/* Book Info Display */}
        <Box
          display="flex"
          flexDirection={{ xs: 'column', sm: 'row' }}
          gap={2}
          alignItems={{ xs: 'center', sm: 'flex-start' }}
          sx={{ mt: 3 }}
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
            flex={1}
            sx={{ textAlign: { xs: 'center', sm: 'left' }, width: { xs: '100%', sm: 'auto' } }}
          >
            <Typography variant="h6" gutterBottom>
              {book.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {book.author || 'Unknown Author'}
            </Typography>
            {book.isbn && (
              <Typography variant="body2" color="text.secondary" gutterBottom>
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
