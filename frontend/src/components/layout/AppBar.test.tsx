import { aBookCard, aBookDetails } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { atCompactViewport } from '@tests/harness/viewport';
import { bookApi } from '@tests/msw/bookApi';
import { libraryApi } from '@tests/msw/libraryApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

/**
 * A book page, with the library primed behind it. The book page's own rails
 * are its tab nav, so it is the page that proves global navigation has a home
 * of its own rather than borrowing one.
 */
const aBookPage = async () => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(...handlers, ...libraryApi([aBookCard({ title: 'The Pragmatic Reader' })]));

  return renderApp({ path: '/book/1' });
};

test('the library is one click away from a book', async () => {
  const screen = await aBookPage();

  await userEvent.click(screen.getByRole('link', { name: 'Library' }));

  await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();
  expect(window.location.pathname).toBe('/library');
});

test('the bar marks which destination you are on', async () => {
  worker.use(...libraryApi([aBookCard()]));

  const screen = await renderApp({ path: '/library' });

  await expect
    .element(screen.getByRole('link', { name: 'Library' }))
    .toHaveAttribute('data-status', 'active');
  await expect
    .element(screen.getByRole('link', { name: 'Home' }))
    .not.toHaveAttribute('data-status', 'active');
});

test('below md the destinations move into the drawer', async () => {
  await atCompactViewport(async () => {
    const screen = await aBookPage();

    // Hidden by `display: none`, so the role query does not reach it at all.
    await expect.element(screen.getByRole('link', { name: 'Library' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Open navigation' }));
    await userEvent.click(screen.getByRole('link', { name: 'Library' }));

    await expect.element(screen.getByText('The Pragmatic Reader')).toBeVisible();
    expect(window.location.pathname).toBe('/library');
  });
});

test('the drawer carries the account entries the account icon hides on a phone', async () => {
  await atCompactViewport(async () => {
    const screen = await aBookPage();

    await expect.element(screen.getByRole('button', { name: 'Account' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Open navigation' }));

    await expect.element(screen.getByRole('link', { name: 'Settings' })).toBeVisible();
    await expect.element(screen.getByRole('button', { name: 'Log out' })).toBeVisible();
  });
});
