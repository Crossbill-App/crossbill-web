import { IconButton, Tooltip, type IconButtonProps } from '@mui/material';
import type { ReactNode } from 'react';

interface IconButtonWithTooltipProps {
  /**
   * The button's name, shown in the tooltip and given to assistive technology
   * as one string — so a reader can say what they see, and a listener hears
   * what the tooltip would have shown. Name the object too, not just the verb:
   * "Delete flashcard" beats "Delete" in a card with three actions.
   */
  label: string;
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
  icon: ReactNode;
  edge?: IconButtonProps['edge'];
  /** MUI's own default; drop to `small` only where a row is genuinely tight. */
  size?: IconButtonProps['size'];
  sx?: IconButtonProps['sx'];
}

export const IconButtonWithTooltip = ({
  label,
  onClick,
  disabled,
  icon,
  edge,
  size = 'medium',
  sx,
}: IconButtonWithTooltipProps) => {
  return (
    <Tooltip title={label}>
      <IconButton
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        size={size}
        edge={edge}
        sx={sx}
      >
        {icon}
      </IconButton>
    </Tooltip>
  );
};
