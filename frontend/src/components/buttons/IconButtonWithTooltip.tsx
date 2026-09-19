import { IconButton, Tooltip, type IconButtonProps } from '@mui/material';
import type { ReactNode } from 'react';

interface IconButtonWithTooltipProps {
  label: string;
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
  icon: ReactNode;
  edge?: IconButtonProps['edge'];
  size?: IconButtonProps['size'];
  /**
   * `inherit` for a button on a surface the app's palette does not describe —
   * the reader's page, whose colour the reader chooses. Left alone it is
   * `action.active`, a fixed black that a dark page swallows.
   */
  color?: IconButtonProps['color'];
  sx?: IconButtonProps['sx'];
}

export const IconButtonWithTooltip = ({
  label,
  onClick,
  disabled,
  icon,
  edge,
  size = 'medium',
  color,
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
        color={color}
        sx={sx}
      >
        {icon}
      </IconButton>
    </Tooltip>
  );
};
