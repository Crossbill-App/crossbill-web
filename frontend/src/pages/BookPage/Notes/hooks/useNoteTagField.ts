import type { TagInBook } from '@/api/generated/model';
import { useCreateTag } from '@/api/generated/tags/tags.ts';
import { useBookMutationHelpers } from '@/hooks/useBookMutationHelpers.ts';

/**
 * Tag-field logic for the note editor: resolve the `(tag | string)` values from
 * the shared tag autocomplete into concrete tags, creating any newly-typed tag
 * immediately (book-wide) so the note can reference it on save.
 *
 * This deliberately differs from the highlight tag field
 * (`useImmediateTagMutation`), which links tags to a highlight immediately via
 * dedicated add/remove endpoints. Notes defer linking to the note's own save,
 * so only tag *creation* is immediate here — the two can't share a hook.
 */
export interface NoteTagField {
  /** Resolve field values into concrete tags, creating any new ones. */
  resolveTags: (
    newValue: (TagInBook | string)[],
    availableTags: TagInBook[]
  ) => Promise<TagInBook[]>;
  /** Whether a tag is currently being created. */
  isCreating: boolean;
}

export const useNoteTagField = (bookId: number): NoteTagField => {
  const { mutationErrorHandler, invalidateBookAndTags } = useBookMutationHelpers(bookId);

  const createTagMutation = useCreateTag({
    mutation: {
      onSuccess: invalidateBookAndTags,
      onError: mutationErrorHandler('create tag'),
    },
  });

  const resolveTags = async (
    newValue: (TagInBook | string)[],
    availableTags: TagInBook[]
  ): Promise<TagInBook[]> => {
    const resolved: TagInBook[] = [];
    for (const item of newValue) {
      if (typeof item !== 'string') {
        if (!resolved.some((tag) => tag.id === item.id)) resolved.push(item);
        continue;
      }
      const name = item.trim();
      if (!name) continue;
      const existing =
        availableTags.find((tag) => tag.name.toLowerCase() === name.toLowerCase()) ??
        resolved.find((tag) => tag.name.toLowerCase() === name.toLowerCase());
      if (existing) {
        if (!resolved.some((tag) => tag.id === existing.id)) resolved.push(existing);
        continue;
      }
      const created = await createTagMutation.mutateAsync({ bookId, data: { name } });
      resolved.push({ id: created.id, name: created.name, tag_group_id: created.tag_group_id });
    }
    return resolved;
  };

  return { resolveTags, isCreating: createTagMutation.isPending };
};
