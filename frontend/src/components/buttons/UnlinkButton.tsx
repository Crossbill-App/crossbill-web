import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { LinkOffIcon } from '@/theme/Icons.tsx';
import type { IconButtonProps } from '@mui/material';

interface UnlinkButtonProps {
  /** The button's name, in the tooltip and for assistive technology. */
  label: string;
  onClick: () => void;
  disabled?: boolean;
  edge?: IconButtonProps['edge'];
  sx?: IconButtonProps['sx'];
}

/**
 * Icon button for removing an entity link. Stops click propagation so it can
 * sit inside clickable cards and rows without triggering their own onClick.
 */
export const UnlinkButton = ({ label, onClick, disabled = false, edge, sx }: UnlinkButtonProps) => (
  <IconButtonWithTooltip
    label={label}
    disabled={disabled}
    edge={edge}
    sx={sx}
    onClick={(event) => {
      event.stopPropagation();
      onClick();
    }}
    icon={<LinkOffIcon fontSize="small" />}
  />
);
