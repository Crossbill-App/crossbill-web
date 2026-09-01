import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { countLabel } from '@/utils/counts.ts';
import { Box } from '@mui/material';
import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  /**
   * This page's search field, if it has one. Which engine sits behind it and
   * when it commits stay the page's business.
   */
  search?: ReactNode;
  /** This page's ordering control, if it has one. Usually a `SortToggle`. */
  sort?: ReactNode;
  /**
   * What this page is showing, and what to call it — `{ value: 42, noun:
   * 'highlight' }`. One number, never a `shown of total` pair: on a book tab
   * the book's unfiltered totals already sit in `BookStatsStrip` above the tab
   * bar, so a pair would print the same number twice (ADR-0003). A page that
   * paginates counts the whole result set rather than the rows on screen —
   * "32 books" on every page of a library of 400 says nothing.
   */
  count?: { value: number; noun: string };
  /**
   * This page's primary action. Width is deliberately unconstrained: the
   * structure tab swaps an icon button for a running-progress row while a
   * batch digest is in flight.
   */
  action?: ReactNode;
}

/**
 * The header a content page leads with — a title row that may carry a result
 * count and a primary action, then a control row holding the search field and
 * the ordering toggle. Every book tab uses it, and so does the library.
 *
 * The count sits on the title's baseline rather than in the control row: next
 * to the search field it reads as part of that widget, and it describes the
 * whole page rather than the search.
 *
 * Render it unconditionally, above any spinner or empty state, so the title
 * never disappears from under the reader while a page loads.
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
