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
  const renames: string[] = [];
  worker.use(
    ...handlers,
    http.delete('/api/v1/tag-groups/:tagGroupId', ({ params }) => {
      deleted.push(Number(params.tagGroupId));
      state.book = { ...state.book, tag_groups: [], tags: [] };
      return new HttpResponse(null, { status: 204 });
    }),
    http.post('/api/v1/tag-groups', async ({ request }) => {
      const body = (await request.json()) as { id: number; name: string };
      renames.push(body.name);
      state.book = { ...state.book, tag_groups: [{ id: body.id, name: body.name }] };
      return HttpResponse.json({ id: body.id, name: body.name });
    })
  );

  const screen = await renderApp({ path: '/book/1/highlights' });
  await expect.element(screen.getByText('Themes')).toBeVisible();

  return { screen, deleted, renames };
};

/** Opens the group's rename editor and returns the field it puts on screen. */
const startRenaming = async (screen: Awaited<ReturnType<typeof renderTagsSidebar>>['screen']) => {
  await userEvent.click(screen.getByRole('button', { name: 'Rename group' }));
  return screen.getByRole('textbox', { name: 'Group name' });
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

  await expect.element(screen.getByText('Themes')).not.toBeInTheDocument();
  expect(deleted).toEqual([5]);
});

/**
 * The rename editor saves itself: there is no confirm button, so both Enter and
 * leaving the field have to commit, and the group has to be wearing its new name
 * once they do.
 */
test.for([
  ['Enter', async () => await userEvent.keyboard('{Enter}')],
  ['leaving the field', async () => await userEvent.tab()],
] as const)('%s renames the group', async ([, commit]) => {
  const { screen, renames } = await renderTagsSidebar();

  await userEvent.fill(await startRenaming(screen), 'Ideas');
  await commit();

  await expect.poll(() => renames).toEqual(['Ideas']);
  await expect.element(screen.getByText('Ideas')).toBeVisible();
});

/**
 * Escape discards, including through the blur it causes itself: the editor
 * closing moves focus, and that blur used to save the name Escape had just
 * thrown away.
 */
test('Escape discards the new name, and the blur it causes saves nothing', async () => {
  const { screen, renames } = await renderTagsSidebar();

  await userEvent.fill(await startRenaming(screen), 'Ideas');
  await userEvent.keyboard('{Escape}');
  await expect.element(screen.getByText('Themes')).toBeVisible();

  await userEvent.tab();

  expect(renames).toEqual([]);
});

test('leaving the name untouched closes the editor without renaming', async () => {
  const { screen, renames } = await renderTagsSidebar();

  await startRenaming(screen);
  await userEvent.tab();

  await expect.element(screen.getByText('Themes')).toBeVisible();
  expect(renames).toEqual([]);
});
