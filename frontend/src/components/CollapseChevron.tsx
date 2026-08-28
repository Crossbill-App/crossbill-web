import { ExpandMoreIcon } from '@/theme/Icons.tsx';
import type { SxProps, Theme } from '@mui/material';

interface CollapseChevronProps {
  isExpanded: boolean;
  sx?: SxProps<Theme>;
}

/**
 * The app's one collapse marker: pointing down when collapsed, up when
 * expanded, matching MUI's `AccordionSummary` expand icon that
 * `CollapsibleSection` renders.
 */
export const CollapseChevron = ({ isExpanded, sx }: CollapseChevronProps) => (
  <ExpandMoreIcon
    sx={[
      {
        transition: 'transform 0.2s ease',
        transform: isExpanded ? 'rotate(180deg)' : 'none',
      },
      ...(Array.isArray(sx) ? sx : [sx]),
    ]}
  />
);
