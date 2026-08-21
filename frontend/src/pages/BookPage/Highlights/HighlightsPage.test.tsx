import { aBookDetails, aChapter, aHighlight } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const REMOVED_TEXT = 'Deleted on the e-reader, kept here';
const KEPT_TEXT = 'The map is not the territory.';

const aBookWithARemovedHighlight = () =>
  bookApi({
    book: aBookDetails({
      chapters: [
        aChapter({
          highlights: [
            aHighlight({ id: 300, text: KEPT_TEXT }),
            aHighlight({ id: 301, text: REMOVED_TEXT, removed_from_devices: true }),
          ],
        }),
      ],
    }),
  });

test('badges only the highlight that was removed from devices', async () => {
  worker.use(...aBookWithARemovedHighlight().handlers);

  const screen = await renderApp({ path: '/book/1/highlights' });

  await expect.element(screen.getByText(REMOVED_TEXT)).toBeVisible();
  await expect.element(screen.getByText(KEPT_TEXT)).toBeVisible();
  expect(await screen.getByText('Not on device').all()).toHaveLength(1);
});

test('the highlight dialog badges a highlight removed from devices', async () => {
  worker.use(...aBookWithARemovedHighlight().handlers);

  const screen = await renderApp({ path: '/book/1/highlights' });
  await userEvent.click(screen.getByRole('button', { name: new RegExp(REMOVED_TEXT) }));

  const dialog = screen.getByRole('dialog');
  await expect.element(dialog.getByText('Not on device')).toBeVisible();
});
