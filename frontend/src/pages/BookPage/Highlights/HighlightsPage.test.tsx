import { getLastSevenDaysFrom } from '@/pages/BookPage/common/highlightDates.ts';
import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test, vi } from 'vitest';
import { page, userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

const expectHighlightInChapter = async (screen: Screen, chapter: string, highlight: string) => {
  await expect
    .element(screen.getByRole('list', { name: `Highlights in ${chapter}` }).getByText(highlight))
    .toBeVisible();
};

const aDateRangeBook = () =>
  aBookDetails({
    bookmarks: [
      {
        id: 900,
        book_id: 1,
        highlight_id: 304,
        created_at: '2026-07-06T00:00:00Z',
      },
    ],
    chapters: [
      aChapter({
        id: 10,
        name: 'Boundary chapter',
        highlights: [
          aHighlight({ id: 301, text: 'At midnight', datetime: '2026-07-05 00:00:00' }),
          aHighlight({ id: 302, text: 'Late that night', datetime: '2026-07-05 23:59:59' }),
          aHighlight({ id: 303, text: 'The next day', datetime: '2026-07-06 00:00:00' }),
        ],
      }),
      aChapter({
        id: 20,
        name: 'Filtered chapter',
        highlights: [
          aHighlight({
            id: 304,
            chapter_id: 20,
            text: 'Before the range',
            datetime: '2026-07-04 23:59:59',
          }),
        ],
      }),
    ],
  });

test('hydrates an inclusive range from the URL and clears each bound independently', async () => {
  const { handlers } = bookApi({ book: aDateRangeBook() });
  worker.use(...handlers);

  const screen = await renderApp({
    path: '/book/1/highlights?from=2026-07-05&to=2026-07-05',
  });

  await expect.element(screen.getByText('At midnight')).toBeVisible();
  await expect.element(screen.getByText('Late that night')).toBeVisible();
  expect(screen.getByText('The next day').elements()).toHaveLength(0);
  expect(screen.getByText('Filtered chapter').elements()).toHaveLength(0);
  await expect.element(screen.getByText('No bookmarks match the active filters.')).toBeVisible();
  await expect.element(screen.getByRole('group', { name: 'From' })).toBeVisible();
  await expect.element(screen.getByRole('group', { name: 'To' })).toBeVisible();

  const fromField = screen.getByRole('group', { name: 'From' });
  const validSearch = window.location.search;
  await userEvent.click(fromField.getByRole('spinbutton', { name: 'Year' }));
  await userEvent.keyboard('1000');
  await expect.element(screen.getByText('Enter a date in the allowed range.')).toBeVisible();
  expect(window.location.search).toBe(validSearch);

  await userEvent.hover(fromField);
  await userEvent.click(fromField.getByRole('button', { name: 'Clear' }));

  await expectHighlightInChapter(screen, 'Filtered chapter', 'Before the range');
  expect(window.location.search).not.toContain('from=');
  expect(window.location.search).toContain('to=2026-07-05');

  const toField = screen.getByRole('group', { name: 'To' });
  await userEvent.hover(toField);
  await userEvent.click(toField.getByRole('button', { name: 'Clear' }));

  await expect.element(screen.getByText('The next day')).toBeVisible();
  await expect.element(screen.getByText('No bookmarks yet.')).not.toBeInTheDocument();
  await expectHighlightInChapter(screen, 'Filtered chapter', 'Before the range');
  expect(window.location.search).not.toContain('from=');
  expect(window.location.search).not.toContain('to=');

  screen.router.history.push('/book/1/highlights?from=not-a-date&to=2026-07-05');
  await expect.poll(() => window.location.search).not.toContain('from=');
  expect(window.location.search).toContain('to=2026-07-05');

  await screen.router.navigate({
    to: '/book/$bookId/highlights',
    params: { bookId: '1' },
    search: { from: '2026-07-06', to: '2026-07-05' },
    replace: true,
  });

  await expect.element(screen.getByText('From must be on or before To.')).toBeVisible();
  await expect.element(screen.getByText('The next day')).toBeVisible();
});

test('composes date, search, tag, and label filters and shows the generic empty state', async () => {
  const matching = aHighlight({
    id: 401,
    text: 'All filters match',
    datetime: '2026-07-05 12:00:00',
    tags: [{ id: 1, name: 'Keep', tag_group_id: null }],
    label: { highlight_style_id: 10, text: 'Important', ui_color: '#ff0000' },
  });
  const searchChapters = [
    aChapter({
      id: 10,
      highlights: [
        matching,
        aHighlight({
          id: 402,
          text: 'Wrong tag',
          datetime: '2026-07-05 12:00:00',
          tags: [{ id: 2, name: 'Other', tag_group_id: null }],
          label: { highlight_style_id: 10 },
        }),
        aHighlight({
          id: 403,
          text: 'Wrong label',
          datetime: '2026-07-05 12:00:00',
          tags: [{ id: 1, name: 'Keep', tag_group_id: null }],
          label: { highlight_style_id: 11 },
        }),
        aHighlight({
          id: 404,
          text: 'Wrong date',
          datetime: '2026-07-06 12:00:00',
          tags: [{ id: 1, name: 'Keep', tag_group_id: null }],
          label: { highlight_style_id: 10 },
        }),
      ],
    }),
  ];
  const { handlers } = bookApi({
    book: aBookDetails({
      tags: [{ id: 1, name: 'Keep', tag_group_id: null }],
      chapters: searchChapters,
    }),
  });
  worker.use(
    ...handlers,
    http.get('/api/v1/books/:bookId/highlights', () =>
      HttpResponse.json({ chapters: searchChapters, total: 4 })
    )
  );

  const screen = await renderApp({
    path: '/book/1/highlights?search=filters&tagId=1&labelId=10&from=2026-07-05&to=2026-07-05',
  });

  await expect.element(screen.getByText('All filters match')).toBeVisible();
  expect(screen.getByText('Wrong tag').elements()).toHaveLength(0);
  expect(screen.getByText('Wrong label').elements()).toHaveLength(0);
  expect(screen.getByText('Wrong date').elements()).toHaveLength(0);

  await screen.router.navigate({
    to: '/book/$bookId/highlights',
    params: { bookId: '1' },
    search: (previous) => ({ ...previous, from: '2026-08-01', to: undefined }),
    replace: true,
  });

  await expect.element(screen.getByText('No highlights match the current filters.')).toBeVisible();

  // One control undoes all four: search, tag, label and date range.
  await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }));

  await expect.element(screen.getByText('All filters match')).toBeVisible();
  await expect.element(screen.getByText('Wrong tag')).toBeVisible();
  await expect.element(screen.getByText('Wrong label')).toBeVisible();
  await expect.element(screen.getByText('Wrong date')).toBeVisible();
});

test('places the preset above mobile tabs and exposes active date filters accessibly', async () => {
  await page.viewport(400, 800);
  try {
    const { handlers } = bookApi({ book: aDateRangeBook() });
    worker.use(...handlers);

    const screen = await renderApp({ path: '/book/1/highlights?to=2026-07-05' });
    // The label counts what is on, so it says which filters are in play.
    const filterButton = screen.getByRole('button', { name: 'Open filters (1 active)' });
    await expect.element(filterButton).toBeVisible();
    await userEvent.click(filterButton);

    await expect.element(screen.getByText('Date highlighted')).toBeVisible();
    await expect.element(screen.getByRole('group', { name: 'From' })).toBeVisible();
    await expect.element(screen.getByRole('group', { name: 'To' })).toBeVisible();
    await expect.element(screen.getByRole('tab', { name: 'Chapters' })).toBeVisible();

    await userEvent.click(screen.getByRole('button', { name: 'Last 7 Days' }));

    await expect.poll(() => window.location.search).toContain(`from=${getLastSevenDaysFrom()}`);
    expect(window.location.search).not.toContain('to=');
  } finally {
    await page.viewport(1440, 900);
  }
});

test('uses the browser regional locale for date field order', async () => {
  const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
  const resolvedOptions = vi
    .spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions')
    .mockImplementation(function (this: Intl.DateTimeFormat) {
      return { ...originalResolvedOptions.call(this), locale: 'fi-FI' };
    });

  try {
    const { handlers } = bookApi({ book: aDateRangeBook() });
    worker.use(...handlers);
    const screen = await renderApp({ path: '/book/1/highlights?from=2026-07-05' });
    const field = screen.getByRole('group', { name: 'From' });
    await expect.element(field).toBeVisible();
    await expect.element(field).toHaveTextContent('05.07.2026');

    const sections = field
      .getByRole('spinbutton')
      .elements()
      .map((element) => element.getAttribute('aria-label'));
    expect(sections).toEqual(['Day', 'Month', 'Year']);
  } finally {
    resolvedOptions.mockRestore();
  }
});

/**
 * The sidebar collapse used to be an `onClick` on a plain `Box`, with a
 * labelled `IconButton` inside it that had no handler of its own — so a
 * keyboard user reached a button that did nothing when activated.
 */
test('the chapters section collapses from the keyboard', async () => {
  const { handlers } = bookApi({ book: aDateRangeBook() });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/highlights' });
  await expect.element(screen.getByRole('list', { name: 'Chapters' })).toBeVisible();

  const toggle = screen.getByRole('button', { name: 'Collapse chapters list' });
  await expect.element(toggle).toHaveAttribute('aria-expanded', 'true');

  (toggle.element() as HTMLElement).focus();
  await userEvent.keyboard('{Enter}');

  await expect
    .element(screen.getByRole('button', { name: 'Expand chapters list' }))
    .toHaveAttribute('aria-expanded', 'false');
  await expect.element(screen.getByRole('list', { name: 'Chapters' })).not.toBeInTheDocument();
});

test('the chapter sidebar carries both counts, so the number does not change with the tab', async () => {
  worker.use(
    ...bookApi({
      book: aBookDetails({
        chapters: [
          aChapter({
            id: 10,
            name: 'On Attention',
            highlights: [
              aHighlight({ id: 301, text: 'A filter, not a spotlight.', flashcards: [] }),
              aHighlight({
                id: 302,
                text: 'Attention is finite.',
                flashcards: [
                  {
                    id: 700,
                    user_id: 1,
                    book_id: 1,
                    highlight_id: 302,
                    chapter_id: 10,
                    question: 'What is attention?',
                    answer: 'A filter.',
                  },
                ],
              }),
            ],
          }),
        ],
      }),
    }).handlers
  );

  const screen = await renderApp({ path: '/book/1/highlights' });
  const chapters = screen.getByRole('list', { name: 'Chapters' });

  await expect.element(chapters.getByText('2 highlights')).toBeVisible();
  await expect.element(chapters.getByText('1 flashcard')).toBeVisible();
});
