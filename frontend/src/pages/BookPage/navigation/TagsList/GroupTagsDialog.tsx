import { TagGroupInBook, TagInBook } from '@/api/generated/model';
import { useUpdateTag } from '@/api/generated/tags/tags.ts';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import {
  Box,
  Button,
  Checkbox,
  List,
  ListItemButton,
  ListItemText,
  TextField,
  Typography,
} from '@mui/material';
import { sortBy } from 'lodash';
import { useMemo, useState } from 'react';

interface GroupTagsDialogProps {
  group: TagGroupInBook;
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  bookId: number;
  open: boolean;
  onClose: () => void;
}

const SEARCH_THRESHOLD = 8;

export const GroupTagsDialog = ({
  group,
  tags,
  tagGroups,
  bookId,
  open,
  onClose,
}: GroupTagsDialogProps) => {
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const updateMutation = useUpdateTag();

  const [orderedTags, setOrderedTags] = useState<TagInBook[]>([]);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Order and initial selection are snapshotted once per opening: `tags` is read
  // here but deliberately not tracked, so tags moving in or out of the group
  // while the dialog is open do not reshuffle the list under the user.
  useResetOnChange([open], () => {
    if (!open) return;
    const inGroup = sortBy(
      tags.filter((tag) => tag.tag_group_id === group.id),
      (tag) => tag.name.toLowerCase()
    );
    const others = sortBy(
      tags.filter((tag) => tag.tag_group_id !== group.id),
      (tag) => tag.name.toLowerCase()
    );
    setOrderedTags([...inGroup, ...others]);
    setCheckedIds(new Set(inGroup.map((tag) => tag.id)));
    setSearch('');
  });

  const groupNameById = useMemo(() => new Map(tagGroups.map((g) => [g.id, g.name])), [tagGroups]);

  const toggle = (tagId: number) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(tagId)) {
        next.delete(tagId);
      } else {
        next.add(tagId);
      }
      return next;
    });
  };

  const pendingChanges = orderedTags.flatMap((tag) => {
    const originalInGroup = tag.tag_group_id === group.id;
    const nowChecked = checkedIds.has(tag.id);
    if (nowChecked && !originalInGroup) {
      return [{ tagId: tag.id, newGroupId: group.id as number | null }];
    }
    if (!nowChecked && originalInGroup) {
      return [{ tagId: tag.id, newGroupId: null }];
    }
    return [];
  });

  const filteredTags = search.trim()
    ? orderedTags.filter((tag) => tag.name.toLowerCase().includes(search.trim().toLowerCase()))
    : orderedTags;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const results = await Promise.allSettled(
        pendingChanges.map((change) =>
          updateMutation.mutateAsync({
            bookId,
            tagId: change.tagId,
            data: { tag_group_id: change.newGroupId },
          })
        )
      );
      cache.tagsChanged(bookId);
      const firstError = results.find((result) => result.status === 'rejected');
      if (firstError) {
        mutationErrorHandler('update tags')((firstError as PromiseRejectedResult).reason);
      }
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <CommonDialog
      open={open}
      onClose={onClose}
      title={`Tags in ${group.name}`}
      maxWidth="xs"
      isLoading={isSaving}
      footerActions={
        <Box sx={{ display: 'flex', gap: 1, width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={pendingChanges.length === 0 || isSaving}
          >
            {pendingChanges.length > 0 ? `Save (${pendingChanges.length})` : 'Save'}
          </Button>
        </Box>
      }
    >
      <Box sx={{ pt: 2 }}>
        {tags.length > SEARCH_THRESHOLD && (
          <TextField
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tags..."
            size="small"
            fullWidth
            sx={{ mb: 1 }}
          />
        )}
        <List disablePadding>
          {filteredTags.map((tag) => {
            const otherGroupId = tag.tag_group_id;
            const secondary =
              otherGroupId != null && otherGroupId !== group.id
                ? `in ${groupNameById.get(otherGroupId) ?? ''}`
                : undefined;
            return (
              <ListItemButton key={tag.id} onClick={() => toggle(tag.id)} dense>
                <Checkbox
                  edge="start"
                  checked={checkedIds.has(tag.id)}
                  tabIndex={-1}
                  disableRipple
                />
                <ListItemText primary={tag.name} secondary={secondary} />
              </ListItemButton>
            );
          })}
          {filteredTags.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ px: 1, py: 2 }}>
              No matching tags.
            </Typography>
          )}
        </List>
      </Box>
    </CommonDialog>
  );
};
