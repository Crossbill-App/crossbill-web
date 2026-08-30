import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';
import { page, userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

const aTaggedBook = () =>
  aBookDetails({
    tags: [{ id: 5, name: 'Method', tag_group_id: null }],
    chapters: [
      aChapter({
        highlights: [
          aHighlight({ id: 301, text: 'Tagged one', tags: [{ id: 5, name: 'Method' }] }),
          aHighlight({ id: 302, text: 'Untagged two' }),
        ],
      }),
    ],
  });

/** Every property `lockBodyScroll` sets, so a leftover from any owner shows up. */
const bodyLockStyles = () => {
  const { overflow, position, top, width } = document.body.style;
  return { overflow, position, top, width };
};

const UNLOCKED = { overflow: '', position: '', top: '', width: '' };

/** The drawer is mobile-only, so these run at a phone width throughout. */
const onMobile = async (body: () => Promise<void>) => {
  await page.viewport(400, 800);
  try {
    await body();
  } finally {
    await page.viewport(1440, 900);
  }
};

const openFilterDrawer = async (): Promise<Screen> => {
  worker.use(...bookApi({ book: aTaggedBook() }).handlers);
  const screen = await renderApp({ path: '/book/1/highlights' });

  await expect.element(screen.getByText('Tagged one')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Open filters' }));
  await expect.element(screen.getByRole('tab', { name: 'Chapters' })).toBeVisible();

  return screen;
};

/**
 * Resolves once the drawer's modal has left the DOM.
 *
 * MUI puts its own body styles back when the exit transition ends, so a check
 * made before that races the very restore these tests are about.
 */
const drawerGone = async (screen: Screen) => {
  await expect.poll(() => screen.getByRole('presentation').elements()).toHaveLength(0);
};

/**
 * Regression for the filter drawer leaving the page unscrollable.
 *
 * MUI's Modal runs a body scroll lock of its own, and it records the styles to
 * restore when its portal mounts — a render *after* `useBodyScrollLock` has
 * already pinned the body. It therefore took `overflow: hidden` for the page's
 * own value and put it back on close, and nothing short of a reload got the
 * page scrolling again. The drawer's lock is ours alone; MUI's is off.
 */
test('picking a filter closes the drawer and leaves the page scrollable', async () => {
  await onMobile(async () => {
    const screen = await openFilterDrawer();
    await userEvent.click(screen.getByRole('tab', { name: 'Tags' }));

    // While it is open the drawer owns the body: pinned, and parked at the
    // scroll position to restore (`0px` here — the list starts at the top).
    expect(bodyLockStyles()).toEqual({
      overflow: 'hidden',
      position: 'fixed',
      top: '0px',
      width: '100%',
    });

    await userEvent.click(screen.getByRole('button', { name: /Method/ }));

    await expect.poll(() => window.location.search).toContain('tagId=5');
    await drawerGone(screen);

    expect(bodyLockStyles()).toEqual(UNLOCKED);
    expect(screen.getByText('Untagged two').elements()).toHaveLength(0);
  });
});

test('closing the drawer by hand leaves the page scrollable', async () => {
  await onMobile(async () => {
    const screen = await openFilterDrawer();

    await userEvent.click(screen.getByRole('button', { name: 'close' }));
    await drawerGone(screen);

    expect(bodyLockStyles()).toEqual(UNLOCKED);
  });
});
