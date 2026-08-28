import { TagGroupInBook, TagInBook } from '@/api/generated/model';
import { Collapsable } from '@/components/animations/Collapsable.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { useSaveStatus } from '@/hooks/useSaveStatus.ts';
import { Box, Typography } from '@mui/material';
import { motion } from 'motion/react';
import { useState } from 'react';

import { GroupTagsDialog } from './GroupTagsDialog.tsx';
import { TagChip } from './TagChip.tsx';
import { TagGroupHeader, TagGroupTitle } from './TagGroupHeader.tsx';

interface TagChipRowProps {
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  selectedTag: number | null | undefined;
  onTagClick: (tagId: number | null) => void;
  onMove: (tagId: number, groupId: number | null) => void;
}

const TagChipRow = ({ tags, tagGroups, selectedTag, onTagClick, onMove }: TagChipRowProps) => (
  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, pt: 0.5 }}>
    {tags.map((tag) => (
      <TagChip
        key={tag.id}
        tag={tag}
        tagGroups={tagGroups}
        selectedTag={selectedTag}
        onTagClick={onTagClick}
        onMove={onMove}
      />
    ))}
  </Box>
);

interface TagGroupSectionProps {
  group: TagGroupInBook;
  tags: TagInBook[];
  allTags: TagInBook[];
  tagGroups: TagGroupInBook[];
  bookId: number;
  isProcessing: boolean;
  selectedTag: number | null | undefined;
  onEditSubmit: (groupId: number, value: string) => Promise<void>;
  onDelete: () => void;
  onTagClick: (tagId: number | null) => void;
  onMove: (tagId: number, groupId: number | null) => void;
}

export const TagGroupSection = ({
  group,
  tags,
  allTags,
  tagGroups,
  bookId,
  isProcessing,
  selectedTag,
  onEditSubmit,
  onDelete,
  onTagClick,
  onMove,
}: TagGroupSectionProps) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const saveStatus = useSaveStatus();

  // The rename commits when the field is left, with nothing else on screen to
  // show it landed.
  const handleEditSubmit = (value: string) => {
    saveStatus.saving();
    onEditSubmit(group.id, value).then(saveStatus.saved, saveStatus.reset);
  };

  const handleConfirmDelete = () => {
    setIsDeleteConfirmOpen(false);
    onDelete();
  };

  return (
    <Box
      sx={(theme) => ({
        p: 1.5,
        bgcolor: theme.customColors.surfaces.tagGroup,
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'divider',
        transition: 'all 0.15s',
      })}
    >
      <TagGroupHeader
        group={group}
        tagCount={tags.length}
        isExpanded={isExpanded}
        onToggleCollapse={() => setIsExpanded(!isExpanded)}
        onEditSubmit={handleEditSubmit}
        onEditTags={() => setIsDialogOpen(true)}
        onDelete={() => setIsDeleteConfirmOpen(true)}
        isProcessing={isProcessing}
        saveStatus={saveStatus.status}
      />
      <Collapsable isExpanded={isExpanded}>
        {tags.length > 0 ? (
          <TagChipRow
            tags={tags}
            tagGroups={tagGroups}
            selectedTag={selectedTag}
            onTagClick={onTagClick}
            onMove={onMove}
          />
        ) : (
          <Box
            onClick={() => setIsDialogOpen(true)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              p: 1.5,
              cursor: 'pointer',
              borderRadius: 1,
              border: '1px dashed',
              borderColor: 'divider',
              '&:hover': { bgcolor: 'action.hover' },
            }}
          >
            <Typography
              variant="body2"
              sx={{
                color: 'text.secondary',
                textAlign: 'center',
                fontSize: '0.75rem',
                fontStyle: 'italic',
              }}
            >
              No tags yet — click to add
            </Typography>
          </Box>
        )}
      </Collapsable>
      <GroupTagsDialog
        group={group}
        tags={allTags}
        tagGroups={tagGroups}
        bookId={bookId}
        open={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
      />
      <ConfirmationDialog
        open={isDeleteConfirmOpen}
        onClose={() => setIsDeleteConfirmOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Tag Group"
        message={
          tags.length > 0
            ? `Delete the group "${group.name}"? Its ${tags.length} ${
                tags.length === 1 ? 'tag stays' : 'tags stay'
              } on your highlights and ${tags.length === 1 ? 'moves' : 'move'} to Ungrouped.`
            : `Delete the group "${group.name}"?`
        }
        confirmText="Delete"
        confirmColor="error"
        isLoading={isProcessing}
      />
    </Box>
  );
};

interface UngroupedTagsSectionProps {
  tags: TagInBook[];
  tagGroups: TagGroupInBook[];
  selectedTag: number | null | undefined;
  onTagClick: (tagId: number | null) => void;
  onMove: (tagId: number, groupId: number | null) => void;
}

export const UngroupedTagsSection = ({
  tags,
  tagGroups,
  selectedTag,
  onTagClick,
  onMove,
}: UngroupedTagsSectionProps) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const shouldHide = tags.length === 0;

  return (
    <motion.div
      initial={false}
      animate={{
        height: shouldHide ? 0 : 'auto',
        opacity: shouldHide ? 0 : 1,
      }}
      transition={{ duration: 0.2 }}
      style={{ overflow: 'hidden' }}
    >
      <Box
        sx={(theme) => ({
          p: 1.5,
          bgcolor: theme.customColors.surfaces.tagUngrouped,
          borderRadius: 1,
          border: '1px dashed',
          borderColor: 'divider',
        })}
      >
        <Box sx={{ mb: isExpanded ? 1 : 0 }}>
          <TagGroupTitle
            title="Ungrouped"
            count={tags.length}
            isExpanded={isExpanded}
            onToggleCollapse={() => setIsExpanded(!isExpanded)}
          />
        </Box>
        <Collapsable isExpanded={isExpanded}>
          <TagChipRow
            tags={tags}
            tagGroups={tagGroups}
            selectedTag={selectedTag}
            onTagClick={onTagClick}
            onMove={onMove}
          />
        </Collapsable>
      </Box>
    </motion.div>
  );
};
