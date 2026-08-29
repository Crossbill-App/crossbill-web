import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { AIIcon } from '@/theme/Icons';
import { Button } from '@mui/material';
import type { ReactNode } from 'react';

interface AIActionButtonProps {
  /** The label, and in `iconOnly` form the tooltip and accessible name. */
  text: string;
  onClick: () => void;
  disabled?: boolean;
  /** Toolbars show the mark alone; everywhere else the label rides with it. */
  iconOnly?: boolean;
  /** Replaces the sparkle where the action has its own mark, e.g. regenerate. */
  icon?: ReactNode;
}

/**
 * Every AI action in the app, so they read as one family: the sparkle is the
 * mark, and the weight never implies how big the job is — a batch across a
 * whole library and a single chapter's summary are the same control.
 */
export const AIActionButton = ({
  text,
  onClick,
  disabled = false,
  iconOnly = false,
  icon,
}: AIActionButtonProps) => {
  if (iconOnly) {
    return (
      <IconButtonWithTooltip
        label={text}
        onClick={onClick}
        disabled={disabled}
        icon={icon ?? <AIIcon />}
      />
    );
  }

  return (
    <Button
      variant="text"
      size="small"
      startIcon={icon ?? <AIIcon />}
      onClick={onClick}
      disabled={disabled}
      sx={{ mb: 1 }}
    >
      {text}
    </Button>
  );
};
