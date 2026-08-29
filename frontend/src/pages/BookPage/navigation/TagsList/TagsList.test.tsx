import { aBookDetails } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const aBookWithTagGroup = () =>
  aBookDetails({
    tag_groups: [{ id: 5, name: 'Themes' }],
    tags: [
      { id: 1, name: 'memory', tag_group_id: 5 },
      { id: 2, name: 'craft', tag_group_id: 5 },
    ],
  });

const renderTagsSidebar = async () => {
  const { handlers, state } = bookApi({ book: aBookWithTagGroup() });
  const deleted: number[] = [];
  worker.use(
    ...handlers,
    http.delete('/api/v1/tag-groups/:tagGroupId', ({ params }) => {
      deleted.push(Number(params.tagGroupId));
      state.book = { ...state.book, tag_groups: [], tags: [] };
      return new HttpResponse(null, { status: 204 });
    })
  );

  const screen = await renderApp({ path: '/book/1/highlights' });
  await expect.element(screen.getByText('Themes')).toBeVisible();

  return { screen, deleted };
};

test('deleting a tag group asks first, naming the group and what happens to its tags', async () => {
  const { screen, deleted } = await renderTagsSidebar();

  await userEvent.click(screen.getByRole('button', { name: 'Delete group' }));

  const dialog = screen.getByRole('alertdialog');
  await expect.element(dialog.getByText(/Delete the group "Themes"\?.*2 tags stay/)).toBeVisible();

  await userEvent.click(dialog.getByRole('button', { name: 'Cancel' }));

  expect(deleted).toEqual([]);
  await expect.element(screen.getByText('Themes')).toBeVisible();
});

test('confirming removes the group', async () => {
  const { screen, deleted } = await renderTagsSidebar();

  await userEvent.click(screen.getByRole('button', { name: 'Delete group' }));
  await userEvent.click(screen.getByRole('alertdialog').getByRole('button', { name: 'Delete' }));

  await expect.element(screen.getByText('No tagged highlights yet.')).toBeVisible();
  expect(deleted).toEqual([5]);
});
