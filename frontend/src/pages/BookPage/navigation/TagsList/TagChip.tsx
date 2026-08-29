import { TagGroupInBook, TagInBook } from '@/api/generated/model';
import { useLongPress, type LongPressCoords } from '@/hooks/useLongPress.ts';
import { Chip } from '@mui/material';
import { useState } from 'react';

import { TagMoveMenu } from './TagMoveMenu.tsx';

interface TagChipProps {
  tag: TagInBook;
  tagGroups: TagGroupInBook[];
  selectedTag: number | null | undefined;
  onTagClick: (tagId: number | null) => void;
  onMove: (tagId: number, groupId: number | null) => void;
}

export const TagChip = ({ tag, tagGroups, selectedTag, onTagClick, onMove }: TagChipProps) => {
  const [anchorPosition, setAnchorPosition] = useState<{ top: number; left: number } | null>(null);
  const isSelected = selectedTag === tag.id;

  const hasMenuItems = tag.tag_group_id != null || tagGroups.length > 0;

  const openMenuAt = (coords: LongPressCoords) => {
    if (!hasMenuItems) return;
    setAnchorPosition({ top: coords.y, left: coords.x });
  };

  const { handlers, consumeClick } = useLongPress(openMenuAt);

  const handleContextMenu = (e: React.MouseEvent) => {
    if (!hasMenuItems) return;
    e.preventDefault();
    e.stopPropagation();
    setAnchorPosition({ top: e.clientY, left: e.clientX });
  };

  return (
    <>
      <Chip
        label={tag.name}
        variant={isSelected ? 'filled' : 'outlined'}
        color={isSelected ? 'primary' : 'default'}
        onContextMenu={handleContextMenu}
        {...handlers}
        onClick={(e) => {
          e.stopPropagation();
          if (consumeClick()) return;
          onTagClick(isSelected ? null : tag.id);
        }}
      />
      <TagMoveMenu
        tag={tag}
        tagGroups={tagGroups}
        anchorPosition={anchorPosition}
        onClose={() => setAnchorPosition(null)}
        onMove={(groupId) => onMove(tag.id, groupId)}
      />
    </>
  );
};
