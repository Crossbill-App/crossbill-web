import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { countLabel } from '@/utils/counts.ts';
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
   * Rows this tab is currently rendering, and what to call them — `{ value: 42,
   * noun: 'highlight' }`. It is the shown count alone, never a `shown of total`
   * pair: the book's unfiltered totals already sit in `BookStatsStrip` above
   * the tab bar, so a pair would print the same number twice (ADR-0003).
   */
  count?: { value: number; noun: string };
  /**
   * This tab's primary action. Width is deliberately unconstrained: the
   * structure tab swaps an icon button for a running-progress row while a
   * batch digest is in flight.
   */
  action?: ReactNode;
}

/**
 * The header every book tab leads with — a title row that may carry a result
 * count and a primary action, then a control row holding the search field and
 * the ordering toggle.
 *
 * The count sits on the title's baseline rather than in the control row: next
 * to the search field it reads as part of that widget, and it describes the
 * whole tab rather than the search.
 *
 * Render it unconditionally, above any spinner or empty state, so the title
 * never disappears from under the reader while a tab loads.
 */
export const PageHeader = ({ title, search, sort, count, action }: PageHeaderProps) => (
  <>
    <Box
      sx={{
        display: 'flex',
        gap: 1,
        alignItems: 'flex-start',
        justifyContent: 'space-between',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, minWidth: 0 }}>
        <PageTitle text={title} />
        {count && <MetadataRow noWrap items={[countLabel(count.value, count.noun)]} />}
      </Box>
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
