import type { WebPublicationManifest } from '@/api/generated/model';
import { aBookDetails } from '@tests/fixtures/book';
import { aManifest } from '@tests/fixtures/publication';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { noPublication, readiumApi } from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { delay, http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const MANIFEST_PATH = '/api/v1/readium/books/:bookId/manifest.json';
const SESSION_PATH = '/api/v1/readium/books/:bookId/session';
const RESOURCE_PATH = '/api/v1/readium/books/:bookId/resources/*';

const elementUnderTheAppBar = () => {
  const { left, top, width, height } = document.querySelector('header')!.getBoundingClientRect();
  return document.elementFromPoint(left + width / 2, top + height / 2);
};

type Screen = Awaited<ReturnType<typeof renderApp>>;

const expectTheReaderOpen = async (screen: Screen) => {
  await expect.element(screen.getByRole('button', { name: 'Close reader' })).toBeVisible();
  expect(screen.router.state.location.pathname).toBe('/book/1/read');
};

const aReadableBook = () =>
  bookApi({
    book: aBookDetails({ title: 'The Pragmatic Reader', author: 'Ada Lovelace' }),
  }).handlers;

/** The book open at its first page, which is where every reading test starts. */
const openTheBook = async () => {
  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByText('Page 1 of 2 · 0%')).toBeVisible();
  return screen;
};

const expectPage = (screen: Screen, label: string) =>
  expect.element(screen.getByText(label), { timeout: 5_000 }).toBeVisible();

test('the book header offers to open the book in the reader', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1' });
  await screen.getByRole('link', { name: 'Open in reader' }).click();

  await expectTheReaderOpen(screen);
});

test('the book navigation offers to read the book', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1' });
  await screen.getByRole('link', { name: 'Read', exact: true }).click();

  await expectTheReaderOpen(screen);
});

test('the reader opens with the book title and a way out', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1/read' });

  await expect.element(screen.getByRole('heading', { name: 'The Pragmatic Reader' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Close reader' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Manage book' })).not.toBeInTheDocument();
  expect(elementUnderTheAppBar()?.closest('header')).toBeNull();
});

test('closing the reader leads to the book page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await renderApp({ path: '/book/1/read' });
  await screen.getByRole('button', { name: 'Close reader' }).click();

  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();
});

test('a session that cannot be started reports it and offers the way back', async () => {
  worker.use(...aReadableBook());
  worker.use(http.post(SESSION_PATH, () => new HttpResponse(null, { status: 500 })));

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(
      screen.getByText(
        'The reader could not start a session for this book. Please try again later.'
      )
    )
    .toBeVisible();

  await screen.getByRole('button', { name: 'Back to book' }).click();

  await expect.element(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeVisible();
});

test('the book opens at its first page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();

  await expect.element(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
});

/** What ReadiumCSS has written into the chapter on screen, of its user settings. */
const userProperty = (name: string) => {
  const frames = [...document.querySelectorAll<HTMLIFrameElement>('iframe')];
  const shown = frames.find((frame) => frame.getBoundingClientRect().width > 0);
  return shown?.contentDocument?.documentElement.style.getPropertyValue(`--USER__${name}`) ?? '';
};

test('a book opens in one column on a wide screen', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  await openTheBook();

  await expect.poll(() => userProperty('colCount')).toBe('1');
});

test('the next button turns the page and the label follows', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectPage(screen, 'Page 2 of 2 · 50%');

  await screen.getByRole('button', { name: 'Previous page' }).click();
  await expectPage(screen, 'Page 1 of 2 · 0%');
});

test('the arrow keys turn the page', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());

  const screen = await openTheBook();

  await userEvent.keyboard('{ArrowRight}');
  await expectPage(screen, 'Page 2 of 2 · 50%');

  await userEvent.keyboard('{ArrowLeft}');
  await expectPage(screen, 'Page 1 of 2 · 0%');
});

test('an arrow key pressed before the book is on screen does not jam it', async () => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi());
  // The chapter alone is late; everything else is served as usual by falling
  // through to the handler registered underneath this one.
  worker.use(
    http.get(RESOURCE_PATH, async ({ params }) => {
      if (String(params[0]) !== 'OEBPS/chapter1.xhtml') return;
      await delay(1_500);
    })
  );

  const screen = await renderApp({ path: '/book/1/read' });
  await expect.element(screen.getByLabelText('Loading the book')).toBeVisible();
  await userEvent.keyboard('{ArrowRight}');

  await expectPage(screen, 'Page 1 of 2 · 0%');
  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectPage(screen, 'Page 2 of 2 · 50%');
});

test('a book with no EPUB explains there is nothing to read', async () => {
  worker.use(...aReadableBook());
  worker.use(...noPublication);

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(
      screen.getByText(
        'This book has no EPUB file, so there is nothing to read here yet. Upload one to read it in the browser.'
      )
    )
    .toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Back to book' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
});

test('a book whose manifest cannot be read says so and offers a retry', async () => {
  worker.use(...aReadableBook());
  worker.use(http.post(SESSION_PATH, () => HttpResponse.json({ expires_in: 900 })));
  worker.use(http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 500 })));

  const screen = await renderApp({ path: '/book/1/read' });

  await expect
    .element(screen.getByText('The book could not be opened. Please try again later.'))
    .toBeVisible();

  worker.use(...readiumApi());
  await screen.getByRole('button', { name: 'Try again' }).click();

  await expectPage(screen, 'Page 1 of 2 · 0%');
});

test('a lapsed session holds the book until it has been renewed', async () => {
  worker.use(...aReadableBook());
  // One second of life, so the cookie has genuinely lapsed by the time the tab
  // is brought back. The scheduled renewal cannot interfere: its floor is five.
  worker.use(...readiumApi({ expiresIn: 1 }));

  const screen = await openTheBook();

  worker.use(
    http.post(SESSION_PATH, async () => {
      await delay(2_000);
      return HttpResponse.json({ expires_in: 900 });
    })
  );
  await new Promise((resolve) => setTimeout(resolve, 1_200));
  window.dispatchEvent(new Event('focus'));

  await expect.element(screen.getByText('Reconnecting…')).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();

  await expect
    .element(screen.getByText('Reconnecting…'), { timeout: 5_000 })
    .not.toBeInTheDocument();
  await expect.element(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
});

const openTheContents = async (screen: Screen) => {
  await screen.getByRole('button', { name: 'Contents' }).click();
  return screen.getByRole('navigation', { name: 'Table of contents' });
};

const closeTheContents = async (screen: Screen) => {
  await screen.getByRole('button', { name: 'Close contents' }).click();
  await expect
    .element(screen.getByRole('navigation', { name: 'Table of contents' }))
    .not.toBeInTheDocument();
};

/** A book on screen at its first page, with its contents drawer open. */
const aBookWithItsContentsOpen = async (manifest?: WebPublicationManifest) => {
  worker.use(...aReadableBook());
  worker.use(...readiumApi({ manifest }));
  const screen = await openTheBook();
  return { screen, contents: await openTheContents(screen) };
};

test('the contents drawer lists the chapters the manifest publishes', async () => {
  const { screen, contents } = await aBookWithItsContentsOpen();

  await expect.element(screen.getByRole('dialog', { name: 'Contents' })).toBeVisible();
  await expect.element(contents.getByText('On Attention')).toBeVisible();
  await expect.element(contents.getByText('Part two')).toBeVisible();
  await expect.element(contents.getByText('On Memory')).toBeVisible();

  // The tree is kept rather than flattened: a chapter sits in from its part.
  const indentOf = (title: string) =>
    (contents.getByText(title).element() as HTMLElement).getBoundingClientRect().left;
  expect(indentOf('On Memory')).toBeGreaterThan(indentOf('Part two'));
  expect(indentOf('Part two')).toBe(indentOf('On Attention'));
});

test('the contents mark the chapter being read, and follow the reader out of it', async () => {
  const { screen, contents } = await aBookWithItsContentsOpen();

  await expect
    .element(contents.getByRole('button', { name: 'On Attention' }))
    .toHaveAttribute('aria-current', 'location');
  await expect
    .element(contents.getByRole('button', { name: 'On Memory' }))
    .not.toHaveAttribute('aria-current');
  await closeTheContents(screen);

  await screen.getByRole('button', { name: 'Next page' }).click();
  await expectPage(screen, 'Page 2 of 2 · 50%');

  const reopened = await openTheContents(screen);
  await expect
    .element(reopened.getByRole('button', { name: 'On Memory' }))
    .toHaveAttribute('aria-current', 'location');
  await expect
    .element(reopened.getByRole('button', { name: 'On Attention' }))
    .not.toHaveAttribute('aria-current');
});

/** The nearest ancestor that actually scrolls, whatever MUI happens to call it. */
const scrollerAbove = (node: HTMLElement): HTMLElement | null => {
  for (let el = node.parentElement; el; el = el.parentElement) {
    if (el.scrollHeight > el.clientHeight + 1) return el;
  }
  return null;
};

/** A book whose contents are long enough to push the chapter being read off screen. */
const aLongToc = () =>
  aManifest({
    toc: [
      ...Array.from({ length: 40 }, (_, index) => ({
        href: `resources/OEBPS/front-matter-${index}.xhtml`,
        title: `Front matter ${index}`,
      })),
      { href: 'resources/OEBPS/chapter1.xhtml', title: 'On Attention' },
      { href: 'resources/OEBPS/chapter2.xhtml', title: 'On Memory' },
    ],
  });

test('the contents open scrolled to the chapter being read', async () => {
  const { contents } = await aBookWithItsContentsOpen(aLongToc());

  const marked = contents.getByRole('button', { name: 'On Attention' });
  await expect.element(marked).toHaveAttribute('aria-current', 'location');

  const node = marked.element() as HTMLElement;
  await expect.poll(() => scrollerAbove(node)?.scrollTop ?? 0).toBeGreaterThan(0);

  // And it is genuinely on screen, which is the thing the reader gets.
  const box = node.getBoundingClientRect();
  expect(box.top).toBeGreaterThanOrEqual(0);
  expect(box.bottom).toBeLessThanOrEqual(window.innerHeight);
});

test('a heading that links nowhere cannot be picked', async () => {
  const { contents } = await aBookWithItsContentsOpen();

  await expect
    .element(contents.getByRole('button', { name: 'Part two' }))
    .toHaveAttribute('aria-disabled', 'true');
  await expect
    .element(contents.getByRole('button', { name: 'On Memory' }))
    .not.toHaveAttribute('aria-disabled');
});

test('an entry the manifest leaves untitled is still named', async () => {
  const { contents } = await aBookWithItsContentsOpen(
    aManifest({ toc: [{ href: 'resources/OEBPS/chapter1.xhtml', title: '' }] })
  );

  await expect
    .element(contents.getByRole('button', { name: 'Untitled' }))
    .toHaveAttribute('aria-current', 'location');
});

test('a book with no contents says so', async () => {
  const { contents } = await aBookWithItsContentsOpen(aManifest({ toc: [] }));

  await expect.element(contents.getByText('This book has no table of contents.')).toBeVisible();
});

test('an arrow key with the contents open does not turn the page behind them', async () => {
  const { screen } = await aBookWithItsContentsOpen();

  await userEvent.keyboard('{ArrowRight}');

  // Settled rather than polled: a turn that got through would land a frame or
  // two later, and an immediate assertion would pass while it was in flight.
  await new Promise((resolve) => setTimeout(resolve, 1_200));
  await expect.element(screen.getByText('Page 1 of 2 · 0%')).toBeVisible();
});
