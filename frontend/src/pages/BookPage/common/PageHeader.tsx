import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { Box } from '@mui/material';
import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  /**
   * This tab's search field, if it has one. Which engine sits behind it and
   * when it commits stay the tab's business.
   */
  search?: ReactNode;
  /** This tab's ordering control, if it has one. Usually a `SortToggle`. */
  sort?: ReactNode;
  /**
   * This tab's primary action. Width is deliberately unconstrained: the
   * structure tab swaps an icon button for a running-progress row while a
   * batch digest is in flight.
   */
  action?: ReactNode;
}

/**
 * The header every book tab leads with — a title row that may carry a primary
 * action, then a control row holding the search field and ordering toggle.
 *
 * Render it unconditionally, above any spinner or empty state, so the title
 * never disappears from under the reader while a tab loads.
 */
export const PageHeader = ({ title, search, sort, action }: PageHeaderProps) => (
  <>
    <Box
      sx={{
        display: 'flex',
        gap: 1,
        alignItems: 'flex-start',
        justifyContent: 'space-between',
      }}
    >
      <PageTitle text={title} />
      {action}
    </Box>

    {(search || sort) && (
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 3 }}>
        <Box sx={{ flexGrow: 1 }}>{search}</Box>
        {sort}
      </Box>
    )}
  </>
);
