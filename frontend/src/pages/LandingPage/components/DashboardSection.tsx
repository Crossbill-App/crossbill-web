import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Box } from '@mui/material';
import { useId, type ReactNode } from 'react';

interface DashboardSectionProps {
  title: string;
  children: ReactNode;
}

/** One band of the dashboard: its heading, and a landmark named by that heading. */
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
