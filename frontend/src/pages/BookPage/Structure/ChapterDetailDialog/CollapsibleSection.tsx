import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { ExpandMoreIcon } from '@/theme/Icons.tsx';
import { Accordion, AccordionDetails, AccordionSummary } from '@mui/material';
import type { ReactNode } from 'react';

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultExpanded?: boolean;
  children: ReactNode;
}

export const CollapsibleSection = ({
  title,
  count,
  defaultExpanded = false,
  children,
}: CollapsibleSectionProps) => {
  const headerText = count !== undefined ? `${title} (${count})` : title;

  return (
    <Accordion
      defaultExpanded={defaultExpanded}
      sx={{
        boxShadow: 'none',
        '&:before': { display: 'none' },
        '&.Mui-expanded': { m: 0 },
        bgcolor: 'transparent',
        borderColor: 'divider',
        '&:last-of-type': { borderBottom: 'none', borderRadius: 0 },
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{
          '&.Mui-expanded': { minHeight: 48 },
          '& .MuiAccordionSummary-content.Mui-expanded': { my: '12px' },
        }}
      >
        <SectionTitle component="h3" gutterBottom={false}>
          {headerText}
        </SectionTitle>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>{children}</AccordionDetails>
    </Accordion>
  );
};
