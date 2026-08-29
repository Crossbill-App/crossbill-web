import type { HighlightLabel } from '@/api/generated/model';
import { getContrastColor } from '@/utils/colorUtils.ts';
import { Box, Chip } from '@mui/material';

interface LabelIndicatorProps {
  label: HighlightLabel | null | undefined;
  onClick?: (event: React.MouseEvent<HTMLElement>) => void;
  size?: 'small' | 'medium';
}

export const LabelIndicator = ({ label, onClick, size = 'small' }: LabelIndicatorProps) => {
  if (!label?.ui_color) {
    return null;
  }

  const isClickable = !!onClick;
  const dotSize = size === 'small' ? 10 : 14;

  if (label.text) {
    return (
      <Chip
        label={label.text}
        onClick={onClick}
        sx={{
          backgroundColor: label.ui_color,
          color: getContrastColor(label.ui_color),
          fontWeight: 500,
          fontSize: size === 'small' ? '0.7rem' : '0.8rem',
          height: size === 'small' ? 22 : 26,
          cursor: isClickable ? 'pointer' : 'default',
          '&:hover': isClickable ? { opacity: 0.85 } : {},
        }}
      />
    );
  }

  return (
    <Box
      component={isClickable ? 'button' : 'span'}
      onClick={onClick}
      aria-label={isClickable ? 'Edit label color' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      sx={{
        width: dotSize,
        height: dotSize,
        borderRadius: '50%',
        backgroundColor: label.ui_color,
        flexShrink: 0,
        border: 'none',
        padding: 0,
        cursor: isClickable ? 'pointer' : 'default',
        transition: 'transform 0.15s',
        '&:hover': isClickable ? { transform: 'scale(1.3)' } : {},
      }}
    />
  );
};
