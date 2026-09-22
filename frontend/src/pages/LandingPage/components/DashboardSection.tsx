import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Box } from '@mui/material';
import { useId, type ReactNode } from 'react';

interface DashboardSectionProps {
  /** The section's heading, and the name its landmark goes by. */
  title: string;
  children: ReactNode;
}

/**
 * One band of the dashboard: its heading, the space below it, and a landmark
 * named by that heading.
 *
 * The bands are built alike — a title, then either the content or a line about
 * what will fill it — so "the one headed Recent books" is the only thing that
 * tells an empty band from the two empty bands beside it. A landmark is what
 * lets a reader jump between them and a test name the one it means.
 */
export const DashboardSection = ({ title, children }: DashboardSectionProps) => {
  const titleId = useId();

  return (
    <Box component="section" aria-labelledby={titleId} sx={{ mb: 6 }}>
      <SectionTitle id={titleId} showDivider>
        {title}
      </SectionTitle>
      {children}
    </Box>
  );
};
