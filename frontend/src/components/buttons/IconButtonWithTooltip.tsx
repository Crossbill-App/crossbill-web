import { IconButton, Tooltip, type IconButtonProps } from '@mui/material';
import type { ReactNode } from 'react';

interface IconButtonWithTooltipProps {
  title: string;
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
  ariaLabel?: string;
  icon: ReactNode;
  edge?: IconButtonProps['edge'];
  /** MUI's own default; drop to `small` only where a row is genuinely tight. */
  size?: IconButtonProps['size'];
  sx?: IconButtonProps['sx'];
}

export const IconButtonWithTooltip = ({
  title,
  onClick,
  disabled,
  ariaLabel,
  icon,
  edge,
  size = 'medium',
  sx,
}: IconButtonWithTooltipProps) => {
  return (
    <Tooltip title={title}>
      <IconButton
        onClick={onClick}
        disabled={disabled}
        aria-label={ariaLabel}
        size={size}
        edge={edge}
        sx={sx}
      >
        {icon}
      </IconButton>
    </Tooltip>
  );
};
