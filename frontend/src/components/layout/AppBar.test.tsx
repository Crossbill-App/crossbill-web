import { aBookCard, aBookDetails } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { atCompactViewport } from '@tests/harness/viewport';
import { bookApi } from '@tests/msw/bookApi';
import { libraryApi } from '@tests/msw/libraryApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';
import { page, userEvent } from 'vitest/browser';

const BOOK_TITLE = 'The Pragmatic Reader';

/**
 * A book page, with the library primed behind it. The book page's own rails
 * are its tab nav, so it is the page that proves global navigation has a home
 * of its own rather than borrowing one.
 *
 * Waits for the book to be on screen: every assertion below is about what the
 * chrome around a loaded page offers, and one made mid-load would pass on an
 * empty page.
 */
const aBookPage = async () => {
  const { handlers } = bookApi({ book: aBookDetails({ title: BOOK_TITLE }) });
  worker.use(...handlers, ...libraryApi([aBookCard({ title: BOOK_TITLE })]));

  const screen = await renderApp({ path: '/book/1' });
  await expect.element(screen.getByRole('heading', { name: BOOK_TITLE })).toBeVisible();

  return screen;
};

/** The dashboard, loaded, with the library primed behind it. */
const aDashboard = async () => {
  worker.use(...libraryApi([aBookCard({ title: BOOK_TITLE })]));

  const screen = await renderApp({ path: '/' });
  await expect.element(screen.getByText('Your reading companion')).toBeVisible();

  return screen;
};

test('the library is one click away from a book', async () => {
  const screen = await aBookPage();

  await userEvent.click(screen.getByRole('link', { name: 'Library', exact: true }));

  await expect.element(screen.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  expect(window.location.pathname).toBe('/library');
});

test('the bar marks which destination you are on', async () => {
  worker.use(...libraryApi([aBookCard()]));

  const screen = await renderApp({ path: '/library' });

  await expect.element(screen.getByRole('navigation', { name: 'Global navigation' })).toBeVisible();
  await expect
    .element(screen.getByRole('link', { name: 'Library', exact: true }))
    .toHaveAttribute('data-status', 'active');
  await expect
    .element(screen.getByRole('link', { name: 'Home', exact: true }))
    .not.toHaveAttribute('data-status', 'active');
});

test('the bar treats a book as part of the library', async () => {
  const screen = await aBookPage();

  await expect
    .element(screen.getByRole('link', { name: 'Library', exact: true }))
    .toHaveAttribute('data-status', 'active');
  await expect
    .element(screen.getByRole('link', { name: 'Home', exact: true }))
    .not.toHaveAttribute('data-status', 'active');
});

test('below md the destinations move into the drawer', async () => {
  await atCompactViewport(async () => {
    const screen = await aDashboard();

    // Hidden by `display: none`, so the role query does not reach it at all.
    await expect
      .element(screen.getByRole('link', { name: 'Library', exact: true }))
      .not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Open navigation' }));
    await expect
      .element(screen.getByRole('navigation', { name: 'Global navigation' }))
      .toBeVisible();
    await userEvent.click(screen.getByRole('link', { name: 'Library', exact: true }));

    await expect.element(screen.getByText(BOOK_TITLE)).toBeVisible();
    expect(window.location.pathname).toBe('/library');
  });
});

test('the drawer carries the account entries the account icon hides on a phone', async () => {
  await atCompactViewport(async () => {
    const screen = await aDashboard();

    await expect.element(screen.getByRole('button', { name: 'Account' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Open navigation' }));

    await expect.element(screen.getByRole('link', { name: 'Settings' })).toBeVisible();
    await expect.element(screen.getByRole('button', { name: 'Log out' })).toBeVisible();
  });
});

test('widening past md closes the phone drawer', async () => {
  await atCompactViewport(async () => {
    const screen = await aDashboard();

    await userEvent.click(screen.getByRole('button', { name: 'Open navigation' }));
    await expect.element(screen.getByRole('link', { name: 'Settings' })).toBeVisible();

    await page.viewport(1440, 900);

    await expect.element(screen.getByRole('link', { name: 'Settings' })).not.toBeInTheDocument();
  });
});

test('a phone leaves a book without opening the drawer', async () => {
  await atCompactViewport(async () => {
    const screen = await aBookPage();

    await userEvent.click(screen.getByRole('link', { name: 'Library', exact: true }));

    await expect
      .element(screen.getByRole('heading', { name: 'Library', exact: true }))
      .toBeVisible();
    expect(window.location.pathname).toBe('/library');
  });
});
