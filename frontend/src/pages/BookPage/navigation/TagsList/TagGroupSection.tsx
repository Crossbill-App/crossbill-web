import { TagGroupInBook, TagInBook } from '@/api/generated/model';
import { Collapsable } from '@/components/animations/Collapsable.tsx';
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
  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
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
  onEditSubmit: (groupId: number, value: string) => void;
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

  return (
    <Box
      sx={(theme) => ({
        p: 1.5,
        bgcolor: theme.customColors.whiteOverlay.group,
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
        onEditSubmit={(value) => onEditSubmit(group.id, value)}
        onEditTags={() => setIsDialogOpen(true)}
        onDelete={onDelete}
        isProcessing={isProcessing}
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
          bgcolor: theme.customColors.whiteOverlay.ungrouped,
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
