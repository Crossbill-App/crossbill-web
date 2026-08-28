import { TagGroupInBook } from '@/api/generated/model';
import { useCommitOnBlur } from '@/hooks/useCommitOnBlur.ts';
import type { SaveStatus } from '@/hooks/useSaveStatus.ts';
import { CollapseChevron } from '@/components/CollapseChevron.tsx';
import { SavedIndicator } from '@/components/SavedIndicator.tsx';
import { DeleteIcon, EditIcon, EditTagsIcon } from '@/theme/Icons.tsx';
import { createAdaptiveHoverStyles, createAdaptiveTouchTarget } from '@/utils/adaptiveHover.ts';
import { Box, IconButton, TextField, Tooltip, Typography } from '@mui/material';
import { useState } from 'react';

interface TagGroupTitleProps {
  title: string;
  count: number;
  isExpanded: boolean;
  onToggleCollapse: () => void;
}

export const TagGroupTitle = ({
  title,
  count,
  isExpanded,
  onToggleCollapse,
}: TagGroupTitleProps) => {
  return (
    <Box
      onClick={onToggleCollapse}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.5,
        flex: 1,
        cursor: 'pointer',
      }}
    >
      <CollapseChevron isExpanded={isExpanded} sx={{ fontSize: 16, color: 'text.secondary' }} />
      <Typography
        variant="subtitle2"
        sx={{
          fontSize: '0.75rem',
          fontWeight: 600,
          color: 'text.secondary',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}
      >
        {title}
        <Typography
          component="span"
          sx={{
            fontSize: '0.7rem',
            fontWeight: 400,
            color: 'text.disabled',
            ml: 0.5,
          }}
        >
          ({count})
        </Typography>
      </Typography>
    </Box>
  );
};

interface TagGroupNameEditFormProps {
  initialValue: string;
  isProcessing: boolean;
  onSubmit: (value: string) => void;
  /** Ends the edit — after Escape, and after leaving the field either way. */
  onClose: () => void;
}

const TagGroupNameEditForm = ({
  initialValue,
  isProcessing,
  onSubmit,
  onClose,
}: TagGroupNameEditFormProps) => {
  // Clicking away blurs the input, which is what saves the name — the shared
  // hook also keeps that from renaming twice when the field is left again
  // while the first rename is still in flight.
  const field = useCommitOnBlur({
    saved: initialValue,
    onCommit: onSubmit,
    onBlur: onClose,
    onCancel: onClose,
  });

  return (
    <TextField
      {...field.inputProps}
      size="small"
      autoFocus
      disabled={isProcessing}
      sx={{ flex: 1, mr: 1 }}
    />
  );
};

interface TagGroupHeaderProps {
  group: TagGroupInBook;
  tagCount: number;
  isExpanded: boolean;
  onToggleCollapse: () => void;
  onEditSubmit: (value: string) => void;
  onEditTags: () => void;
  onDelete: () => void;
  isProcessing: boolean;
  /** Rename saves itself when the field is left, so the save is marked here. */
  saveStatus: SaveStatus;
}

export const TagGroupHeader = ({
  group,
  tagCount,
  isExpanded,
  onToggleCollapse,
  onEditSubmit,
  onEditTags,
  onDelete,
  isProcessing,
  saveStatus,
}: TagGroupHeaderProps) => {
  const [isEditing, setIsEditing] = useState(false);

  const adaptiveStyles = createAdaptiveHoverStyles({
    actionsClassName: 'group-actions',
    transitionDuration: 0.15,
  });
  const touchTarget = createAdaptiveTouchTarget();

  const handleEditSubmit = (value: string) => {
    onEditSubmit(value);
    setIsEditing(false);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        mb: isExpanded ? 1 : 0,
        cursor: 'pointer',
        ...adaptiveStyles.container,
      }}
    >
      {isEditing ? (
        <TagGroupNameEditForm
          initialValue={group.name}
          isProcessing={isProcessing}
          onSubmit={handleEditSubmit}
          onClose={() => setIsEditing(false)}
        />
      ) : (
        <TagGroupTitle
          title={group.name}
          count={tagCount}
          isExpanded={isExpanded}
          onToggleCollapse={onToggleCollapse}
        />
      )}
      {!isEditing && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <SavedIndicator status={saveStatus} sx={{ minHeight: 0 }} />
          <Box
            className="group-actions"
            sx={{
              ...adaptiveStyles.actions,
              gap: 0.25,
            }}
          >
          <Tooltip title="Edit tags">
            <span>
              <IconButton
                size="small"
                aria-label="Edit tags"
                onClick={(e) => {
                  e.stopPropagation();
                  onEditTags();
                }}
                sx={{ ...touchTarget, color: 'text.disabled' }}
              >
                <EditTagsIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Rename group">
            <span>
              <IconButton
                size="small"
                aria-label="Rename group"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsEditing(true);
                }}
                sx={{ ...touchTarget, color: 'text.disabled' }}
              >
                <EditIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Delete group">
            <span>
              <IconButton
                size="small"
                aria-label="Delete group"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
                disabled={isProcessing}
                sx={{ ...touchTarget, color: 'text.disabled' }}
              >
                <DeleteIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </span>
            </Tooltip>
          </Box>
        </Box>
      )}
    </Box>
  );
};
