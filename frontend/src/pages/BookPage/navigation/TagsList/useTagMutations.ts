import { getGetBookDetailsQueryKey } from '@/api/generated/books/books.ts';
import { TagInBook } from '@/api/generated/model';
import {
  useCreateOrUpdateTagGroup,
  useDeleteTagGroup,
  useUpdateTag,
} from '@/api/generated/tags/tags.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

export const useTagMutations = (bookId: number) => {
  const queryClient = useQueryClient();
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const [isProcessing, setIsProcessing] = useState(false);

  const updateTagMutation = useUpdateTag({
    mutation: {
      onMutate: async (variables: {
        bookId: number;
        tagId: number;
        data: { tag_group_id?: number | null };
      }) => {
        await queryClient.cancelQueries({
          queryKey: getGetBookDetailsQueryKey(bookId),
        });
        const previousBook = queryClient.getQueryData(getGetBookDetailsQueryKey(bookId));
        queryClient.setQueryData(getGetBookDetailsQueryKey(bookId), (old: unknown) => {
          if (!old || typeof old !== 'object') return old;
          const bookData = old as { tags: TagInBook[] };
          return {
            ...bookData,
            tags: bookData.tags.map((tag: TagInBook) =>
              tag.id === variables.tagId
                ? { ...tag, tag_group_id: variables.data.tag_group_id }
                : tag
            ),
          };
        });
        return { previousBook };
      },
      onSuccess: (updatedTag: TagInBook) => {
        queryClient.setQueryData(getGetBookDetailsQueryKey(bookId), (old: unknown) => {
          if (!old || typeof old !== 'object') return old;
          const bookData = old as { tags: TagInBook[] };
          return {
            ...bookData,
            tags: bookData.tags.map((tag: TagInBook) =>
              tag.id === updatedTag.id ? updatedTag : tag
            ),
          };
        });
      },
      onError: (
        error: unknown,
        _variables: unknown,
        context: { previousBook: unknown } | undefined
      ) => {
        if (context?.previousBook) {
          queryClient.setQueryData(getGetBookDetailsQueryKey(bookId), context.previousBook);
        }
        mutationErrorHandler('move tag')(error);
      },
    },
  });

  const createOrUpdateGroupMutation = useCreateOrUpdateTagGroup({
    mutation: {
      onSuccess: () => cache.tagsChanged(bookId),
      onError: mutationErrorHandler('save tag group'),
    },
  });

  const deleteGroupMutation = useDeleteTagGroup({
    mutation: {
      onSuccess: () => cache.tagsChanged(bookId),
      onError: mutationErrorHandler('delete tag group'),
    },
  });

  const moveTagToGroup = (tagId: number, newGroupId: number | null) => {
    updateTagMutation.mutate({
      bookId,
      tagId,
      data: { tag_group_id: newGroupId },
    });
  };

  const handleEditSubmit = async (groupId: number, value: string) => {
    if (!value.trim()) {
      return;
    }

    setIsProcessing(true);
    try {
      await createOrUpdateGroupMutation.mutateAsync({
        data: {
          book_id: bookId,
          id: groupId,
          name: value.trim(),
        },
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDeleteGroup = async (groupId: number) => {
    setIsProcessing(true);
    try {
      await deleteGroupMutation.mutateAsync({
        tagGroupId: groupId,
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAddGroup = async (newGroupName: string, onSuccess: () => void) => {
    if (!newGroupName.trim()) {
      onSuccess();
      return null;
    }

    setIsProcessing(true);
    try {
      const created = await createOrUpdateGroupMutation.mutateAsync({
        data: {
          book_id: bookId,
          name: newGroupName.trim(),
        },
      });
      onSuccess();
      return created.id;
    } catch {
      return null;
    } finally {
      setIsProcessing(false);
    }
  };

  return {
    isProcessing,
    handleEditSubmit,
    handleAddGroup,
    handleDeleteGroup,
    moveTagToGroup,
  };
};
