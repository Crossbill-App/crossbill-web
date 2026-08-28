import { CollapseChevron } from '@/components/CollapseChevron.tsx';
import type { SvgIconComponent } from '@mui/icons-material';
import { Box, IconButton, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface SidebarSectionCollapse {
  isExpanded: boolean;
  onToggle: () => void;
  /** Names the section in the button's label: "Collapse chapters list". */
  sectionLabel: string;
  /** Id of the region the header controls, for `aria-controls`. */
  controlsId?: string;
}

interface SidebarSectionHeaderProps {
  icon: SvgIconComponent;
  title: string;
  action?: ReactNode;
  /** Turns the header into the control for the section beneath it. */
  collapse?: SidebarSectionCollapse;
}

/**
 * The heading every sidebar section leads with, optionally doubling as its
 * collapse control.
 *
 * The toggle lives on the `IconButton`, so a keyboard user reaching it
 * actually operates the section; the row's own handler is a mouse convenience
 * on top of that, which is why it sits on a plain container rather than a
 * button.
 */
export const SidebarSectionHeader = ({
  icon: Icon,
  title,
  action,
  collapse,
}: SidebarSectionHeaderProps) => (
  <Box
    onClick={collapse?.onToggle}
    sx={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      mb: 2,
      flexShrink: 0,
      ...(collapse && { cursor: 'pointer' }),
    }}
  >
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Icon sx={{ fontSize: 18, color: 'primary.main' }} />
      <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 600 }}>
        {title}
      </Typography>
    </Box>
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      {action}
      {collapse && (
        <IconButton
          size="small"
          aria-label={`${collapse.isExpanded ? 'Collapse' : 'Expand'} ${collapse.sectionLabel}`}
          aria-expanded={collapse.isExpanded}
          aria-controls={collapse.controlsId}
          onClick={(event) => {
            event.stopPropagation();
            collapse.onToggle();
          }}
        >
          <CollapseChevron isExpanded={collapse.isExpanded} sx={{ display: 'block' }} />
        </IconButton>
      )}
    </Box>
  </Box>
);
