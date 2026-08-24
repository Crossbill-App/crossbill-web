import { useDialogHorizontalNavigation } from '@/components/dialogs/useDialogHorizontalNavigation';
import { expect, test, vi } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

/** Stand-in for a paged detail modal, e.g. HighlightViewDialog. */
const PagedDialog = ({ onNavigate }: { onNavigate: (newIndex: number) => void }) => {
  useDialogHorizontalNavigation({ open: true, currentIndex: 1, totalCount: 3, onNavigate });
  return <div>Paged dialog body</div>;
};

/**
 * Stand-in for a dialog with no paging of its own, e.g. a NoteViewDialog
 * opened as a nested "View note" preview rather than from a paged list —
 * `totalCount` defaults to 1 and `onNavigate` is omitted, so it has no
 * navigation.
 */
const UnpagedNestedDialog = () => {
  useDialogHorizontalNavigation({ open: true, currentIndex: 0, totalCount: 1 });
  return <div>Nested dialog body</div>;
};

/**
 * Regression for #620: a nested dialog with no navigation of its own must
 * still shadow the paged dialog beneath it, or arrow keys leak through to
 * page a dialog the user can no longer see.
 */
test('a nested dialog with no navigation blocks arrow keys from reaching the dialog beneath it', async () => {
  const onNavigate = vi.fn();
  await render(<PagedDialog onNavigate={onNavigate} />);
  await render(<UnpagedNestedDialog />);

  await userEvent.keyboard('{ArrowRight}');

  expect(onNavigate).not.toHaveBeenCalled();
});

test('closing the nested dialog restores arrow-key paging on the dialog beneath it', async () => {
  const onNavigate = vi.fn();
  await render(<PagedDialog onNavigate={onNavigate} />);
  const nested = await render(<UnpagedNestedDialog />);

  await nested.unmount();
  await userEvent.keyboard('{ArrowRight}');

  expect(onNavigate).toHaveBeenCalledWith(2);
});
