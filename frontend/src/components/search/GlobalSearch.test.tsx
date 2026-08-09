import { aBookDetails } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { settingsWithEmbeddings } from '@tests/msw/auth';
import { bookApi } from '@tests/msw/bookApi';
import { semanticSearchApi } from '@tests/msw/semanticSearchApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';

const PLACEHOLDER = 'Search everything…';

test('the app bar offers a global search field when embeddings are on', async () => {
  const { handlers } = bookApi({ book: aBookDetails() });
  worker.use(settingsWithEmbeddings(true), ...handlers, ...semanticSearchApi({}));

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
