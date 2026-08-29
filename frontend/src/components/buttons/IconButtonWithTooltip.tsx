import { IconButton, Tooltip, type IconButtonProps } from '@mui/material';
import type { ReactNode } from 'react';

interface IconButtonWithTooltipProps {
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
