import { TagGroupInBook, TagInBook } from '@/api/generated/model';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { AddIcon, TagIcon } from '@/theme/Icons.tsx';
import { Box, Button, IconButton, Tooltip } from '@mui/material';
import { sortBy } from 'lodash';
import { useState } from 'react';

import { SidebarSectionHeader } from '../SidebarSectionHeader.tsx';
import { AddGroupForm } from './AddGroupForm.tsx';
import { TagGroupSection, UngroupedTagsSection } from './TagGroupSection.tsx';
import { useTagMutations } from './useTagMutations.ts';

interface TagsProps {
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  bookId: number;
  selectedTag?: number | null;
  onTagClick: (tagId: number | null) => void;
  hideTitle?: boolean;
  hideEmptyGroups?: boolean;
}

export const TagsList = ({
  tags,
  tagGroups,
  bookId,
  selectedTag,
  onTagClick,
  hideTitle,
  hideEmptyGroups,
}: TagsProps) => {
  const [showAddGroup, setShowAddGroup] = useState(false);
  const [newGroupIds, setNewGroupIds] = useState<Set<number>>(new Set());

  const { handleEditSubmit, handleAddGroup, handleDeleteGroup, moveTagToGroup, isProcessing } =
    useTagMutations(bookId);

  const submitNewGroup = async (name: string) => {
    const createdId = await handleAddGroup(name, () => setShowAddGroup(false));
    if (createdId != null) {
      setNewGroupIds((prev) => new Set(prev).add(createdId));
    }
  };

  const sortedTags = [...tags].sort((a, b) => a.name.localeCompare(b.name));

  const ungroupedTags = sortedTags.filter((tag) => !tag.tag_group_id);
  const groupedTags = sortBy(
    tagGroups.map((group) => ({
      group,
      tags: sortedTags.filter((tag) => tag.tag_group_id === group.id),
    })),
    'group.name'
  );

  return (
    <Box>
      {!hideTitle ? (
        <SidebarSectionHeader
          icon={TagIcon}
          title="Tags"
          action={
            <Tooltip title="Add new group">
              <IconButton
                size="small"
                onClick={() => setShowAddGroup(true)}
                sx={{ color: 'text.secondary', padding: 0.5 }}
              >
                <AddIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          }
        />
      ) : (
        !showAddGroup && (
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            <Button
              size="small"
              startIcon={<AddIcon sx={{ fontSize: 16 }} />}
              onClick={() => setShowAddGroup(true)}
              sx={{ color: 'text.secondary', fontSize: '0.75rem' }}
            >
              Add group
            </Button>
          </Box>
        )
      )}

      <AddGroupForm
        isVisible={showAddGroup}
        isProcessing={isProcessing}
        onSubmit={(newName: string) => void submitNewGroup(newName)}
        onCancel={() => {
          setShowAddGroup(false);
        }}
      />

      {tags.length > 0 ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {groupedTags.map(({ group, tags: groupTags }) =>
            hideEmptyGroups && groupTags.length === 0 && !newGroupIds.has(group.id) ? null : (
              <TagGroupSection
                key={group.id}
                group={group}
                tags={groupTags}
                allTags={tags}
                tagGroups={tagGroups}
                bookId={bookId}
                isProcessing={isProcessing}
                selectedTag={selectedTag}
                onEditSubmit={handleEditSubmit}
                onDelete={() => void handleDeleteGroup(group.id)}
                onTagClick={onTagClick}
                onMove={moveTagToGroup}
              />
            )
          )}

          {hideEmptyGroups && ungroupedTags.length === 0 ? null : (
            <UngroupedTagsSection
              tags={ungroupedTags}
              tagGroups={tagGroups}
              selectedTag={selectedTag}
              onTagClick={onTagClick}
              onMove={moveTagToGroup}
            />
          )}
        </Box>
      ) : (
        <EmptyStateText>No tagged highlights yet.</EmptyStateText>
      )}
    </Box>
  );
};
