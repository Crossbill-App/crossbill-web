import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { CopyIcon, DeleteIcon, EditIcon, LinkIcon } from '@/theme/Icons.tsx';
import { useTranslation } from 'react-i18next';

interface NoteToolbarProps {
  onCopyLink: () => void;
  onEdit: () => void;
  onCopy: () => void;
  onDelete: () => void;
  disabled?: boolean;
}

export const NoteToolbar = ({
  onCopyLink,
  onEdit,
  onCopy,
  onDelete,
  disabled = false,
}: NoteToolbarProps) => {
  const { t } = useTranslation();
  return (
    <DialogToolbar>
      <IconButtonWithTooltip
        label={t('notes.noteToolbar.copyLink')}
        onClick={onCopyLink}
        disabled={disabled}
        icon={<LinkIcon />}
      />
      <IconButtonWithTooltip
        label={t('notes.shared.editNote')}
        onClick={onEdit}
        disabled={disabled}
        icon={<EditIcon />}
      />
      <IconButtonWithTooltip
        label={t('notes.noteToolbar.copyContent')}
        onClick={onCopy}
        disabled={disabled}
        icon={<CopyIcon />}
      />
      <IconButtonWithTooltip
        label={t('notes.noteToolbar.delete')}
        onClick={onDelete}
        disabled={disabled}
        icon={<DeleteIcon />}
      />
    </DialogToolbar>
  );
};
