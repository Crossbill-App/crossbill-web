import { TagGroupHeader } from '@/pages/BookPage/navigation/TagsList/TagGroupHeader';
import { expect, test, vi } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

/**
 * The header alone, with stub callbacks — no router and no network, so these
 * run in a fraction of the time a route-level test takes.
 */
const renderHeader = async (isProcessing = false) => {
  const onEditSubmit = vi.fn();
  const screen = await render(
    <>
      <TagGroupHeader
        group={{ id: 1, name: 'Themes' }}
        tagCount={3}
        isExpanded
        onToggleCollapse={() => {}}
        onEditSubmit={onEditSubmit}
        onEditTags={() => {}}
        onDelete={() => {}}
        isProcessing={isProcessing}
        saveStatus="idle"
      />
      <button>elsewhere</button>
    </>
  );

  return { screen, onEditSubmit, elsewhere: screen.getByRole('button', { name: 'elsewhere' }) };
};

const startRenaming = async (screen: Awaited<ReturnType<typeof renderHeader>>['screen']) => {
  await userEvent.click(screen.getByRole('button', { name: 'Rename group' }));
  return screen.getByRole('textbox');
};

test('Enter renames the group and closes the editor', async () => {
  const { screen, onEditSubmit } = await renderHeader();

  await userEvent.fill(await startRenaming(screen), 'Ideas');
  await userEvent.keyboard('{Enter}');

  expect(onEditSubmit).toHaveBeenCalledExactlyOnceWith('Ideas');
  await expect.element(screen.getByText('Themes')).toBeVisible();
});

test('clicking away renames the group', async () => {
  const { screen, onEditSubmit, elsewhere } = await renderHeader();

  await userEvent.fill(await startRenaming(screen), 'Ideas');
  await userEvent.click(elsewhere);

  expect(onEditSubmit).toHaveBeenCalledExactlyOnceWith('Ideas');
});

test('Escape discards the new name', async () => {
  const { screen, onEditSubmit, elsewhere } = await renderHeader();

  await userEvent.fill(await startRenaming(screen), 'Ideas');
  await userEvent.keyboard('{Escape}');

  await expect.element(screen.getByText('Themes')).toBeVisible();

  // The blur that follows Escape must not rename either.
  await userEvent.click(elsewhere);
  expect(onEditSubmit).not.toHaveBeenCalled();
});

test('leaving the name untouched closes the editor without renaming', async () => {
  const { screen, onEditSubmit, elsewhere } = await renderHeader();

  await startRenaming(screen);
  await userEvent.click(elsewhere);

  expect(onEditSubmit).not.toHaveBeenCalled();
  await expect.element(screen.getByText('Themes')).toBeVisible();
});
