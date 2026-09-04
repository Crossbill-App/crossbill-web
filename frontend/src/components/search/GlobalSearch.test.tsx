import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { aNote } from '@tests/fixtures/notes';
import { aBookHit, aDigestHit, aHighlightHit, aNoteHit } from '@tests/fixtures/search';
import { renderApp } from '@tests/harness/renderApp';
import { atCompactViewport } from '@tests/harness/viewport';
import { settingsWithEmbeddings } from '@tests/msw/auth';
import { bookApi } from '@tests/msw/bookApi';
import { coversApi } from '@tests/msw/covers';
import { globalSearchApi } from '@tests/msw/searchApi';
import { worker } from '@tests/msw/worker';
import { delay, http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const PLACEHOLDER = 'Search...';

test('the app bar offers a global search field when embeddings are on', async () => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(settingsWithEmbeddings(true), ...handlers, ...globalSearchApi({}));

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByPlaceholder(PLACEHOLDER)).toBeVisible();
});

test('the app bar has no search field when embeddings are off', async () => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(settingsWithEmbeddings(false), ...handlers);

  const screen = await renderApp({ path: '/book/1' });

  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();
  await expect.element(screen.getByPlaceholder(PLACEHOLDER)).not.toBeInTheDocument();
});

/** Renders the app at a book page with the app bar's search wired to `results`. */
const renderWithResults = async (
  results: Parameters<typeof globalSearchApi>[0],
  book = aBookDetails()
) => {
  const { handlers } = bookApi({ book, notes: [] });
  worker.use(settingsWithEmbeddings(true), ...handlers, ...globalSearchApi(results));
  return renderApp({ path: '/book/1' });
};

const search = async (screen: Awaited<ReturnType<typeof renderApp>>, query: string) => {
  await userEvent.fill(screen.getByPlaceholder(PLACEHOLDER), query);
  await userEvent.keyboard('{Enter}');
};

/**
 * A single highlight hit wired to a book with a matching chapter, shared by
 * the desktop and mobile click-through tests.
 */
const renderWithHighlightResult = () =>
  renderWithResults(
    {
      attention: {
        highlights: [aHighlightHit({ id: 300, text: 'The map is not the territory.' })],
      },
    },
    aBookDetails({
      chapters: [aChapter({ id: 10, highlights: [aHighlight({ id: 300 })] })],
    })
  );

test('results from every type are ranked together, not grouped by type', async () => {
  const screen = await renderWithResults({
    attention: {
      highlights: [aHighlightHit({ id: 300, score: 0.5, text: 'A middling highlight' })],
      notes: [aNoteHit({ id: 100, score: 0.9, title: 'The best note' })],
      digests: [aDigestHit({ id: 500, score: 0.7, summary: 'A decent chapter' })],
    },
  });

  await search(screen, 'attention');

  const rows = screen.getByRole('option');
  await expect.element(rows.nth(0)).toHaveTextContent('The best note');
  await expect.element(rows.nth(1)).toHaveTextContent('A decent chapter');
  await expect.element(rows.nth(2)).toHaveTextContent('A middling highlight');
});

test('the list is capped at ten rows after merging, not per type', async () => {
  // Six of each type: under the cap individually, twelve combined. A
  // per-type cap applied before merging would let all twelve through.
  // Interleaved scores also mean the true global top ten mixes both types,
  // rather than favouring whichever type happens to be capped last.
  const screen = await renderWithResults({
    attention: {
      highlights: Array.from({ length: 6 }, (_, index) =>
        aHighlightHit({ id: 300 + index, score: 0.95 - index * 0.1, text: `Highlight ${index}` })
      ),
      notes: Array.from({ length: 6 }, (_, index) =>
        aNoteHit({ id: 100 + index, score: 0.9 - index * 0.1, title: `Note ${index}` })
      ),
    },
  });

  await search(screen, 'attention');

  const rows = screen.getByRole('option');
  await expect.element(rows.nth(9)).toBeVisible();
  expect(rows.elements()).toHaveLength(10);

  // Ranks 1-10 by score: Highlight 0/1/2/3/4 and Note 0/1/2/3/4.
  await expect.element(screen.getByText('Highlight 4')).toBeVisible();
  await expect.element(screen.getByText('Note 4')).toBeVisible();
  // Ranks 11-12, excluded only by the merged cap.
  await expect.element(screen.getByText('Highlight 5')).not.toBeInTheDocument();
  await expect.element(screen.getByText('Note 5')).not.toBeInTheDocument();
  await expect.element(screen.getByText('Showing top 10')).toBeVisible();
});

test('a book matched by name leads the list, whatever the ranked hits scored', async () => {
  const screen = await renderWithResults({
    attention: {
      books: [aBookHit({ id: 7, title: 'Deep Work', author: 'Cal Newport' })],
      highlights: [aHighlightHit({ id: 300, score: 0.99, text: 'A near-perfect highlight' })],
    },
  });

  await search(screen, 'attention');

  const rows = screen.getByRole('option');
  await expect.element(rows.nth(0)).toHaveTextContent('Deep Work');
  await expect.element(rows.nth(0)).toHaveTextContent('Cal Newport');
  await expect.element(rows.nth(0).getByText('Book')).toBeVisible();
  await expect.element(rows.nth(1)).toHaveTextContent('A near-perfect highlight');
});

test('books sit above the ten-row cap, which the ranked rows alone fill', async () => {
  const screen = await renderWithResults({
    attention: {
      books: [aBookHit({ id: 7, title: 'Deep Work' }), aBookHit({ id: 8, title: 'Shallow Work' })],
      highlights: Array.from({ length: 12 }, (_, index) =>
        aHighlightHit({ id: 300 + index, score: 0.95 - index * 0.01, text: `Highlight ${index}` })
      ),
    },
  });

  await search(screen, 'attention');

  const rows = screen.getByRole('option');
  await expect.element(rows.nth(11)).toBeVisible();
  expect(rows.elements()).toHaveLength(12);
  await expect.element(screen.getByText('Showing top 10')).toBeVisible();
});

test('a list the books lengthen but the cap never touched claims no truncation', async () => {
  const screen = await renderWithResults({
    attention: {
      books: [aBookHit({ id: 7, title: 'Deep Work' }), aBookHit({ id: 8, title: 'Shallow Work' })],
      highlights: Array.from({ length: 3 }, (_, index) =>
        aHighlightHit({ id: 300 + index, score: 0.9 - index * 0.01, text: `Highlight ${index}` })
      ),
    },
  });

  await search(screen, 'attention');

  await expect.element(screen.getByRole('option').nth(4)).toBeVisible();
  await expect.element(screen.getByText('Showing top 10')).not.toBeInTheDocument();
});

test('a note with no linked book is left out, having no page to open', async () => {
  const screen = await renderWithResults({
    attention: {
      notes: [
        aNoteHit({ id: 100, score: 0.9, title: 'Homeless note', books: [] }),
        aNoteHit({ id: 101, score: 0.8, title: 'Anchored note' }),
      ],
    },
  });

  await search(screen, 'attention');

  await expect.element(screen.getByText('Anchored note')).toBeVisible();
  await expect.element(screen.getByText('Homeless note')).not.toBeInTheDocument();
});

test('a row with a cover renders it as an image from the covers endpoint', async () => {
  const { handlers } = bookApi({ book: aBookDetails(), notes: [] });
  worker.use(
    settingsWithEmbeddings(true),
    ...handlers,
    ...coversApi(),
    ...globalSearchApi({
      attention: {
        highlights: [aHighlightHit({ id: 300, cover_file: 'cover-one.jpg' })],
      },
    })
  );
  const screen = await renderApp({ path: '/book/1' });

  await search(screen, 'attention');

  const cover = screen.getByRole('option').first().getByRole('img');
  await expect.element(cover).toBeVisible();
  await expect
    .poll(() => cover.element().getAttribute('src'))
    .toContain('/api/v1/covers/cover-one.jpg');
});

test('the initial fetch shows a spinner before any rows arrive', async () => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(
    settingsWithEmbeddings(true),
    ...handlers,
    // Never resolves: `waitForIdle` in the test harness bounds its wait, so
    // this can't hang the run, and it keeps `isFetching` true for the whole
    // test without a fake timer.
    http.get('/api/v1/search', async () => {
      await delay('infinite');
    })
  );
  const screen = await renderApp({ path: '/book/1' });

  await search(screen, 'attention');

  await expect.element(screen.getByRole('progressbar', { name: 'Searching' })).toBeVisible();
});

test('clicking a highlight row opens the highlight dialog on the book page', async () => {
  const screen = await renderWithHighlightResult();

  await search(screen, 'attention');
  await userEvent.click(screen.getByRole('option').first());

  await expect
    .element(screen.getByRole('dialog').getByText('The map is not the territory.'))
    .toBeVisible();
  expect(window.location.pathname).toBe('/book/1/highlights');
  expect(window.location.search).toContain('highlightId=300');
});

test('clicking a note row opens the note dialog on the book page', async () => {
  const { handlers } = bookApi({
    book: aBookDetails(),
    notes: [aNote({ id: 100, title: 'Ada Lovelace' })],
  });
  worker.use(
    settingsWithEmbeddings(true),
    ...handlers,
    ...globalSearchApi({ attention: { notes: [aNoteHit({ id: 100, title: 'Ada Lovelace' })] } })
  );
  const screen = await renderApp({ path: '/book/1' });

  await search(screen, 'attention');
  await userEvent.click(screen.getByRole('option').first());

  await expect.element(screen.getByRole('dialog').getByText('Ada Lovelace')).toBeVisible();
  expect(window.location.pathname).toBe('/book/1/notes');
  expect(window.location.search).toContain('noteId=100');
});

test('clicking a chapter row opens the chapter dialog on the book page', async () => {
  const screen = await renderWithResults(
    {
      attention: {
        digests: [aDigestHit({ id: 500, chapter_id: 10, chapter_name: 'On Attention' })],
      },
    },
    aBookDetails({ chapters: [aChapter({ id: 10, name: 'On Attention' })] })
  );

  await search(screen, 'attention');
  await userEvent.click(screen.getByRole('option').first());

  await expect.element(screen.getByRole('dialog').getByText('On Attention')).toBeVisible();
  expect(window.location.pathname).toBe('/book/1/structure');
  expect(window.location.search).toContain('chapterId=10');
});

test('clicking a book row opens that book and closes the dropdown', async () => {
  const screen = await renderWithResults({
    attention: { books: [aBookHit({ id: 7, title: 'Deep Work' })] },
  });

  await search(screen, 'attention');
  await userEvent.click(screen.getByRole('option').first());

  expect(window.location.pathname).toBe('/book/7/structure');
  await expect.element(screen.getByRole('listbox')).not.toBeInTheDocument();
});

test('Enter opens the row the arrow keys landed on', async () => {
  const screen = await renderWithResults({
    attention: { books: [aBookHit({ id: 7, title: 'Deep Work' })] },
  });

  await search(screen, 'attention');
  await expect.element(screen.getByRole('option').first()).toBeVisible();

  await userEvent.keyboard('{ArrowDown}');
  await userEvent.keyboard('{Enter}');

  expect(window.location.pathname).toBe('/book/7/structure');
});

test('Escape closes the dropdown and keeps the query, a second Escape clears it', async () => {
  const screen = await renderWithResults({
    attention: { notes: [aNoteHit({ id: 100, title: 'Ada Lovelace' })] },
  });

  await search(screen, 'attention');
  await expect.element(screen.getByRole('option').first()).toBeVisible();

  await userEvent.keyboard('{Escape}');

  await expect.element(screen.getByRole('listbox')).not.toBeInTheDocument();
  await expect.element(screen.getByPlaceholder(PLACEHOLDER)).toHaveValue('attention');

  await userEvent.keyboard('{Escape}');

  await expect.element(screen.getByPlaceholder(PLACEHOLDER)).toHaveValue('');
});

test('tabbing away closes the dropdown instead of reopening it', async () => {
  const screen = await renderWithResults({
    attention: { notes: [aNoteHit({ id: 100, title: 'Ada Lovelace' })] },
  });

  await search(screen, 'attention');
  await expect.element(screen.getByRole('option').first()).toBeVisible();

  // The clear button is focusable, and it belongs to the widget, so the first
  // Tab is not a dismissal.
  await userEvent.tab();
  await expect.element(screen.getByRole('button', { name: 'Clear search' })).toHaveFocus();
  await expect.element(screen.getByRole('listbox')).toBeVisible();

  await userEvent.tab();

  await expect.element(screen.getByRole('listbox')).not.toBeInTheDocument();
});

test('arrowing down points aria-activedescendant at the first row', async () => {
  const screen = await renderWithResults({
    attention: { notes: [aNoteHit({ id: 100, title: 'Ada Lovelace' })] },
  });

  await search(screen, 'attention');
  const firstRow = screen.getByRole('option').first();
  await expect.element(firstRow).toBeVisible();
  const firstRowId = firstRow.element().id;

  await userEvent.keyboard('{ArrowDown}');

  await expect
    .element(screen.getByPlaceholder(PLACEHOLDER))
    .toHaveAttribute('aria-activedescendant', firstRowId);
});

test('a query that matches nothing says so, rather than showing an empty box', async () => {
  const screen = await renderWithResults({});

  await search(screen, 'attention');

  await expect.element(screen.getByText('No matches')).toBeVisible();
});

test('a failing search reports the failure', async () => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(
    settingsWithEmbeddings(true),
    ...handlers,
    http.get('/api/v1/search', () => new HttpResponse(null, { status: 500 }))
  );
  const screen = await renderApp({ path: '/book/1' });

  await search(screen, 'attention');

  await expect.element(screen.getByText('Search failed. Try again.')).toBeVisible();
});

/**
 * Renders a book page below `md` with embeddings on, where only the search
 * icon (not the inline field) is in the DOM, shared by the tests that only
 * care about that icon rather than a query's results.
 */
const renderCompactSearchIcon = (
  fn: (screen: Awaited<ReturnType<typeof renderApp>>) => Promise<void>
) => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(settingsWithEmbeddings(true), ...handlers);
  return atCompactViewport(async () => {
    const screen = await renderApp({ path: '/book/1' });
    await fn(screen);
  });
};

test('below md, a search icon replaces the inline field', async () => {
  await renderCompactSearchIcon(async (screen) => {
    await expect.element(screen.getByRole('button', { name: 'Search' })).toBeVisible();
    await expect.element(screen.getByPlaceholder(PLACEHOLDER)).not.toBeInTheDocument();
  });
});

test('tapping the search icon opens a full-screen dialog with the field', async () => {
  await renderCompactSearchIcon(async (screen) => {
    await userEvent.click(screen.getByRole('button', { name: 'Search' }));

    await expect.element(screen.getByRole('dialog')).toBeVisible();
    await expect.element(screen.getByPlaceholder(PLACEHOLDER)).toBeVisible();
  });
});

test('the field is focused when the mobile dialog opens, so the keyboard appears without a second tap', async () => {
  await renderCompactSearchIcon(async (screen) => {
    await userEvent.click(screen.getByRole('button', { name: 'Search' }));

    await expect.element(screen.getByPlaceholder(PLACEHOLDER)).toHaveFocus();
  });
});

test('a query in the mobile dialog shows the same result rows as desktop', async () => {
  await atCompactViewport(async () => {
    const screen = await renderWithResults({
      attention: { notes: [aNoteHit({ id: 100, title: 'Ada Lovelace' })] },
    });

    await userEvent.click(screen.getByRole('button', { name: 'Search' }));
    await search(screen, 'attention');

    await expect.element(screen.getByRole('option')).toHaveTextContent('Ada Lovelace');
  });
});

test('selecting a row in the mobile dialog navigates and closes it', async () => {
  await atCompactViewport(async () => {
    const screen = await renderWithHighlightResult();

    await userEvent.click(screen.getByRole('button', { name: 'Search' }));
    await search(screen, 'attention');
    await userEvent.click(screen.getByRole('option').first());

    expect(window.location.pathname).toBe('/book/1/highlights');
    expect(window.location.search).toContain('highlightId=300');
    await expect.element(screen.getByPlaceholder(PLACEHOLDER)).not.toBeInTheDocument();
  });
});

test('a search with no results can still be dismissed via the close button', async () => {
  await atCompactViewport(async () => {
    const screen = await renderWithResults({});

    await userEvent.click(screen.getByRole('button', { name: 'Search' }));
    await search(screen, 'attention');
    await expect.element(screen.getByText('No matches')).toBeVisible();

    await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }));

    await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument();
  });
});

test('with embeddings off, no search icon appears below md', async () => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(settingsWithEmbeddings(false), ...handlers);

  await atCompactViewport(async () => {
    const screen = await renderApp({ path: '/book/1' });

    await expect
      .element(screen.getByRole('heading', { name: 'The Pragmatic Reader' }))
      .toBeVisible();
    await expect.element(screen.getByRole('button', { name: 'Search' })).not.toBeInTheDocument();
  });
});
