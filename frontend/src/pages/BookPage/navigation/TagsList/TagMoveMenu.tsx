import { TagGroupInBook, TagInBook } from '@/api/generated/model';
import { LinkOffIcon } from '@/theme/Icons.tsx';
import { ListItemIcon, ListItemText, Menu, MenuItem } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface TagMoveMenuProps {
  tag: TagInBook;
  tagGroups: TagGroupInBook[];
  anchorPosition: { top: number; left: number } | null;
  onClose: () => void;
  onMove: (groupId: number | null) => void;
}

export const TagMoveMenu = ({
  tag,
  tagGroups,
  anchorPosition,
  onClose,
  onMove,
}: TagMoveMenuProps) => {
  const { t } = useTranslation();
  const targetGroups = tagGroups.filter((group) => group.id !== tag.tag_group_id);

  const handleMove = (groupId: number | null) => {
    onMove(groupId);
    onClose();
  };

  return (
    <Menu
      open={anchorPosition !== null}
      onClose={onClose}
      anchorReference="anchorPosition"
      anchorPosition={anchorPosition ?? undefined}
    >
      {targetGroups.map((group) => (
        <MenuItem key={group.id} onClick={() => handleMove(group.id)}>
          <ListItemText primary={t('book.navigation.tags.moveMenu.moveTo', { name: group.name })} />
        </MenuItem>
      ))}
      {tag.tag_group_id != null && (
        <MenuItem onClick={() => handleMove(null)}>
          <ListItemIcon>
            <LinkOffIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary={t('book.navigation.tags.moveMenu.removeFromGroup')} />
        </MenuItem>
      )}
    </Menu>
  );
};
