import { DialogTabs } from '@/components/dialogs/DialogTabs';
import { useDialogHorizontalNavigation } from '@/components/dialogs/useDialogHorizontalNavigation';
import { expect, test, vi } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

/**
 * Stand-in for the entity detail modals: tabs nested inside a dialog whose
 * arrow keys page to the previous/next entity.
 */
const NavigableDialog = ({ onNavigate }: { onNavigate: (newIndex: number) => void }) => {
  useDialogHorizontalNavigation({
    open: true,
    currentIndex: 1,
    totalCount: 3,
    onNavigate,
  });

  return (
    <div>
      <button type="button">Body control</button>
      <DialogTabs
        tabs={[
          { key: 'notes', label: 'Notes', count: 1, content: <div>Linked notes</div> },
          { key: 'flashcards', label: 'Flashcards', count: 2, content: <div>Flashcard list</div> },
        ]}
      />
    </div>
  );
};

/** Opens the dialog on the first tab and walks focus one tab to the right. */
const renderAndArrowToSecondTab = async (onNavigate: (newIndex: number) => void) => {
  const screen = await render(<NavigableDialog onNavigate={onNavigate} />);

  await userEvent.click(screen.getByRole('tab', { name: 'Notes (1)' }));
  await userEvent.keyboard('{ArrowRight}');

  return screen;
};

test('arrow keys move between tabs instead of paging the dialog', async () => {
  const onNavigate = vi.fn();
  const screen = await renderAndArrowToSecondTab(onNavigate);

  await expect.element(screen.getByRole('tab', { name: 'Flashcards (2)' })).toHaveFocus();
  expect(onNavigate).not.toHaveBeenCalled();
});

test('a tab reached by keyboard can be activated to reveal its panel', async () => {
  const onNavigate = vi.fn();
  const screen = await renderAndArrowToSecondTab(onNavigate);

  await userEvent.keyboard('{Enter}');

  await expect.element(screen.getByText('Flashcard list')).toBeInTheDocument();
  await expect.element(screen.getByText('Linked notes')).not.toBeInTheDocument();
  expect(onNavigate).not.toHaveBeenCalled();
});

test('arrow keys outside the tab strip still page the dialog', async () => {
  const onNavigate = vi.fn();
  const screen = await render(<NavigableDialog onNavigate={onNavigate} />);

  await userEvent.click(screen.getByRole('button', { name: 'Body control' }));
  await userEvent.keyboard('{ArrowRight}');

  expect(onNavigate).toHaveBeenCalledWith(2);
});

test('the panel is named by the tab that opened it', async () => {
  const screen = await render(<NavigableDialog onNavigate={vi.fn()} />);

  const panel = screen.getByRole('tabpanel');
  const tab = screen.getByRole('tab', { name: 'Notes (1)' });

  await expect.element(panel).toHaveAccessibleName('Notes (1)');
  await expect.element(tab).toHaveAttribute('aria-controls', panel.element().id);
});
