/* eslint-disable */
// PROTOTYPE — throwaway. Lives on branch prototype/landing-due-cards only.
// Four landing-page treatments of due flashcards, switched by ?variant=A|B|C|D.
// A/B/C open the real ReviewDialog (grades are recorded in the local DB).
// D embeds the review card with a stub queue: nothing is recorded.
import { useGetDueFlashcards } from '@/api/generated/flashcards/flashcards.ts';
import type { DueFlashcard } from '@/api/generated/model';
import { ProgressBar } from '@/components/dialogs/ProgressBar.tsx';
import { ReviewCard } from '@/components/features/flashcards/review/ReviewCard.tsx';
import { ReviewDialog } from '@/components/features/flashcards/review/ReviewDialog.tsx';
import { ReadingActivityGrid } from '@/components/reading/ReadingActivityGrid.tsx';
import { Stat } from '@/components/reading/Stat.tsx';
import { ReviewIcon } from '@/theme/Icons.tsx';
import { tabularNums } from '@/theme/theme.ts';
import { Box, Button, Typography } from '@mui/material';
import { Link } from '@tanstack/react-router';
import { groupBy } from 'lodash';
import { useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardSection } from '../components/DashboardSection.tsx';
import { booksByDay, summary } from '../components/ReadingActivity.tsx';
import { RECENT_ROW_WIDTH } from '../components/RecentBooks.tsx';
import { RecentCaptures } from '../components/RecentCaptures.tsx';
import { useReadingActivity } from '../components/landingQueries.ts';

export const DUE_VARIANTS = [
  { key: 'A', name: 'Count strip in the hero' },
  { key: 'B', name: 'Section before captures, per book' },
  { key: 'C', name: 'Column beside captures' },
  { key: 'D', name: 'Review embedded in the page' },
  { key: 'E', name: 'Beside a narrower activity grid' },
  { key: 'F', name: 'Full row: count + next card + books' },
];

interface BookDue {
  bookId: number;
  title: string;
  count: number;
}

const useDue = () => {
  const query = useGetDueFlashcards({ limit: 1000 });
  const cards = query.data?.items ?? [];
  const books = useMemo<BookDue[]>(
    () =>
      Object.values(groupBy(cards, (c) => c.book_id))
        .map((group) => ({
          bookId: group[0].book_id,
          title: group[0].book_title,
          count: group.length,
        }))
        .sort((a, b) => b.count - a.count),
    [cards]
  );
  return { cards, books, total: query.data?.total ?? 0, fetchedAt: query.dataUpdatedAt };
};

/** Opens the real review modal: every book when bookId is left out. */
const useReview = () => {
  const [open, setOpen] = useState<{ bookId?: number } | null>(null);
  const dialog = open && <ReviewDialog bookId={open.bookId} onClose={() => setOpen(null)} />;
  return { start: (bookId?: number) => setOpen({ bookId }), dialog };
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

const BookLink = ({ book }: { book: BookDue }) => (
  <Link
    to="/book/$bookId/flashcards"
    params={{ bookId: String(book.bookId) }}
    style={{ color: 'inherit', textDecoration: 'none' }}
  >
    <Typography variant="body1" sx={{ '&:hover': { textDecoration: 'underline' } }} noWrap>
      {book.title}
    </Typography>
  </Link>
);

// --- A: a single strip under the page title -------------------------------

export const HeroStrip = () => {
  const { total, books } = useDue();
  const review = useReview();
  if (total === 0) return null;

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 6, mt: -2 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          pl: 2.5,
          pr: 1,
          py: 1,
          borderRadius: 999,
          border: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <ReviewIcon sx={{ color: 'primary.main' }} />
        <Typography variant="body1">
          <Box component="strong" sx={tabularNums}>
            {plural(total, 'card', 'cards')}
          </Box>{' '}
          to review from {plural(books.length, 'book', 'books')}
        </Typography>
        <Button variant="contained" onClick={() => review.start()} sx={{ borderRadius: 999 }}>
          Review
        </Button>
      </Box>
      {review.dialog}
    </Box>
  );
};

// --- B: a dashboard section listing each book's due count ---------------

export const PerBookSection = () => {
  const { total, books } = useDue();
  const review = useReview();
  if (total === 0) return null;

  return (
    <DashboardSection title="Due for review">
      <Box
        sx={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          mt: 2,
          mb: 1,
        }}
      >
        <Typography variant="body1" sx={{ color: 'text.secondary' }}>
          {plural(total, 'card is', 'cards are')} waiting. Each takes a few seconds.
        </Typography>
        <Button variant="contained" startIcon={<ReviewIcon />} onClick={() => review.start()}>
          Review all ({total})
        </Button>
      </Box>
      <Box component="ul" sx={{ listStyle: 'none', p: 0, m: 0 }}>
        {books.map((book) => (
          <Box
            component="li"
            key={book.bookId}
            sx={{
              display: 'grid',
              gridTemplateColumns: '1fr auto auto',
              alignItems: 'center',
              gap: 2,
              px: 1.5,
              py: 1,
              borderBottom: 1,
              borderColor: 'divider',
            }}
          >
            <BookLink book={book} />
            <Typography variant="body2" sx={{ color: 'text.secondary', ...tabularNums }}>
              {plural(book.count, 'card', 'cards')}
            </Typography>
            <Button size="small" onClick={() => review.start(book.bookId)}>
              Review
            </Button>
          </Box>
        ))}
      </Box>
      {review.dialog}
    </DashboardSection>
  );
};

// --- C: captures keep the main column; review takes a side column -------

const SidePanel = () => {
  const { total, books, cards } = useDue();
  const review = useReview();
  const next = cards[0];

  return (
    <Box
      component="aside"
      sx={{
        position: { md: 'sticky' },
        top: { md: 96 },
        border: 1,
        borderColor: 'divider',
        borderRadius: 2,
        p: 3,
        bgcolor: 'background.paper',
      }}
    >
      {total === 0 ? (
        <Typography variant="body1" sx={{ color: 'text.secondary' }}>
          Nothing to review. New cards appear here as you read.
        </Typography>
      ) : (
        <>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Due for review
          </Typography>
          <Typography sx={{ fontSize: '3rem', lineHeight: 1.1, fontWeight: 600, ...tabularNums }}>
            {total}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
            from {plural(books.length, 'book', 'books')}
          </Typography>

          {next && (
            <Box sx={{ borderLeft: 3, borderColor: 'primary.main', pl: 1.5, mb: 2 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Next up · {next.book_title}
              </Typography>
              <Typography variant="body1" sx={{ fontStyle: 'italic' }}>
                {next.question}
              </Typography>
            </Box>
          )}

          <Button
            fullWidth
            variant="contained"
            startIcon={<ReviewIcon />}
            onClick={() => review.start()}
          >
            Start review
          </Button>

          <Box sx={{ mt: 2 }}>
            {books.slice(0, 5).map((book) => (
              <Box
                key={book.bookId}
                sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, py: 0.5 }}
              >
                <BookLink book={book} />
                <Typography variant="body2" sx={{ color: 'text.secondary', ...tabularNums }}>
                  {book.count}
                </Typography>
              </Box>
            ))}
          </Box>
        </>
      )}
      {review.dialog}
    </Box>
  );
};

export const CapturesWithSideColumn = () => (
  <Box
    sx={{
      display: 'grid',
      gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 2fr) minmax(280px, 1fr)' },
      gap: { xs: 0, md: 6 },
      alignItems: 'start',
    }}
  >
    <RecentCaptures />
    <Box sx={{ order: { xs: -1, md: 0 }, mb: { xs: 6, md: 0 } }}>
      <SidePanel />
    </Box>
  </Box>
);

// --- D: the review card itself, inline, with a stub queue ----------------

export const EmbeddedReview = () => {
  const { cards, total, fetchedAt } = useDue();
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  if (total === 0) return null;

  const next = () => {
    setRevealed(false);
    setIndex((i) => i + 1);
  };
  const card: DueFlashcard | undefined = cards[index];

  let body: ReactNode;
  if (!card) {
    body = (
      <Typography variant="body1" sx={{ color: 'text.secondary', py: 3 }}>
        All caught up. (Stub queue: reload to start over.)
      </Typography>
    );
  } else {
    body = (
      <ReviewCard
        key={card.id}
        card={{ ...card, fetchedAt }}
        revealed={revealed}
        onReveal={() => setRevealed(true)}
        onGrade={next}
        onEdit={next}
        onSuspend={next}
      />
    );
  }

  return (
    <DashboardSection title="Review">
      <Box sx={{ mt: 2, border: 1, borderColor: 'divider', borderRadius: 2, overflow: 'hidden' }}>
        <ProgressBar currentIndex={Math.min(index, total - 1)} totalCount={total} />
        <Box sx={{ p: { xs: 2, md: 4 } }}>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2, ...tabularNums }}>
            {Math.min(index + 1, total)} of {total} · stub: grades are not recorded
          </Typography>
          {body}
        </Box>
      </Box>
    </DashboardSection>
  );
};

// --- shared by E and F: the count and the first card, as the call to action --

const BigCount = ({ total, books }: { total: number; books: number }) => (
  <Box>
    <Typography sx={{ fontSize: '3.5rem', lineHeight: 1, fontWeight: 600, ...tabularNums }}>
      {total}
    </Typography>
    <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
      {total === 1 ? 'card' : 'cards'} due from {plural(books, 'book', 'books')}
    </Typography>
  </Box>
);

const NextUp = ({
  card,
  onStart,
  large,
}: {
  card: DueFlashcard;
  onStart: () => void;
  large?: boolean;
}) => (
  <Box
    component="button"
    onClick={onStart}
    sx={{
      all: 'unset',
      cursor: 'pointer',
      display: 'block',
      boxSizing: 'border-box',
      width: '100%',
      borderLeft: 3,
      borderColor: 'primary.main',
      pl: 2,
      py: 0.5,
      '&:hover .next-question': { color: 'primary.main' },
    }}
  >
    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>
      Next up · {card.chapter_name ? `${card.book_title} · ${card.chapter_name}` : card.book_title}
    </Typography>
    <Typography
      className="next-question"
      variant={large ? 'h2' : 'body1'}
      component="p"
      sx={{ transition: 'color 0.2s', fontStyle: large ? 'normal' : 'italic' }}
    >
      {card.question}
    </Typography>
  </Box>
);

// --- E: activity grid shrinks, review panel beside it, stats under the grid --

export const ActivityWithReview = () => {
  const { t } = useTranslation();
  const { data } = useReadingActivity();
  const activity = data?.activity;
  const stats = data?.stats;
  const read = useMemo(() => booksByDay(t, activity), [t, activity]);
  const due = useDue();
  const review = useReview();
  const next = due.cards[0];

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', lg: 'auto minmax(320px, 1fr)' },
        columnGap: 6,
        maxWidth: { lg: `${RECENT_ROW_WIDTH}px` },
        alignItems: 'start',
      }}
    >
      <DashboardSection title={t('landing.readingActivity.title')}>
        <Box sx={{ mt: 2 }}>
          <ReadingActivityGrid activity={activity ?? null} dayNote={(date) => read.get(date)} />
        </Box>
        {stats && (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: 'repeat(2, 1fr)',
                sm: 'repeat(3, 1fr)',
                lg: 'repeat(6, auto)',
              },
              justifyContent: 'space-between',
              gap: 2,
              mt: 3,
            }}
          >
            {summary(t, stats).map((stat) => (
              <Stat key={stat.label} value={stat.value} label={stat.label} />
            ))}
          </Box>
        )}
      </DashboardSection>

      {due.total > 0 && (
        <Box sx={{ order: { xs: -1, lg: 0 } }}>
          <DashboardSection title="Due for review">
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, mt: 2 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  justifyContent: 'space-between',
                  gap: 2,
                }}
              >
                <BigCount total={due.total} books={due.books.length} />
                <Button
                  variant="contained"
                  startIcon={<ReviewIcon />}
                  onClick={() => review.start()}
                >
                  Start review
                </Button>
              </Box>
              {next && <NextUp card={next} onStart={() => review.start()} />}
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {due.books
                  .slice(0, 3)
                  .map((b) => `${b.title} (${b.count})`)
                  .join(' · ')}
                {due.books.length > 3 && ` · and ${due.books.length - 3} more`}
              </Typography>
            </Box>
          </DashboardSection>
        </Box>
      )}
      {review.dialog}
    </Box>
  );
};

// --- F: B's full row, with C's count and first card leading it ------------

export const FullRowReview = () => {
  const due = useDue();
  const review = useReview();
  const next = due.cards[0];
  if (due.total === 0) return null;

  return (
    <DashboardSection title="Due for review">
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            md: '200px minmax(0, 1fr)',
            lg: '200px minmax(0, 1.4fr) minmax(0, 1fr)',
          },
          gap: { xs: 3, md: 5 },
          alignItems: 'start',
          mt: 3,
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start' }}>
          <BigCount total={due.total} books={due.books.length} />
          <Button variant="contained" startIcon={<ReviewIcon />} onClick={() => review.start()}>
            Review all
          </Button>
        </Box>

        {next && <NextUp card={next} onStart={() => review.start()} large />}

        <Box
          component="ul"
          sx={{ listStyle: 'none', p: 0, m: 0, gridColumn: { md: '1 / -1', lg: 'auto' } }}
        >
          {due.books.slice(0, 5).map((book) => (
            <Box
              component="li"
              key={book.bookId}
              sx={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) auto auto',
                alignItems: 'center',
                gap: 1.5,
                py: 0.5,
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <BookLink book={book} />
              <Typography variant="body2" sx={{ color: 'text.secondary', ...tabularNums }}>
                {book.count}
              </Typography>
              <Button size="small" onClick={() => review.start(book.bookId)}>
                Review
              </Button>
            </Box>
          ))}
          {due.books.length > 5 && (
            <Typography variant="body2" sx={{ color: 'text.secondary', pt: 1 }}>
              and {plural(due.books.length - 5, 'more book', 'more books')}
            </Typography>
          )}
        </Box>
      </Box>
      {review.dialog}
    </DashboardSection>
  );
};
