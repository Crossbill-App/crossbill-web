import { useCommitOnBlur } from '@/hooks/useCommitOnBlur';
import { expect, test, vi } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

/** A field over a server value, the way the gist and digest answers use it. */
const Probe = ({ saved, onCommit }: { saved: string; onCommit: (value: string) => void }) => {
  const field = useCommitOnBlur({ saved, onCommit });

  return (
    <>
      <input aria-label="field" {...field.inputProps} />
      <button>elsewhere</button>
    </>
  );
};

/** A probe over `saved`, with the two things every test reaches for. */
const renderProbe = async (saved = '') => {
  const onCommit = vi.fn();
  const screen = await render(<Probe saved={saved} onCommit={onCommit} />);

  return {
    screen,
    onCommit,
    field: screen.getByRole('textbox', { name: 'field' }),
    elsewhere: screen.getByRole('button', { name: 'elsewhere' }),
  };
};

test('a value that reaches the server takes over from the local text', async () => {
  const { screen, onCommit, field, elsewhere } = await renderProbe();

  await userEvent.fill(field, 'typed');
  await userEvent.click(elsewhere);
  expect(onCommit).toHaveBeenCalledExactlyOnceWith('typed');

  // The refetch lands: same text, now from the server.
  await screen.rerender(<Probe saved="typed" onCommit={onCommit} />);
  await expect.element(field).toHaveValue('typed');

  // A later change made elsewhere is shown, because no local text is held.
  await screen.rerender(<Probe saved="edited elsewhere" onCommit={onCommit} />);
  await expect.element(field).toHaveValue('edited elsewhere');
});

test('a refetch landing mid-sentence does not overwrite what is being typed', async () => {
  const { screen, onCommit, field } = await renderProbe();

  await userEvent.fill(field, 'half a thou');

  // The #259 race: a response arrives while the reader is still typing.
  await screen.rerender(<Probe saved="from the server" onCommit={onCommit} />);

  await expect.element(field).toHaveValue('half a thou');
  expect(onCommit).not.toHaveBeenCalled();
});

test('leaving the field again before the refetch does not save twice', async () => {
  const { onCommit, field, elsewhere } = await renderProbe();

  await userEvent.fill(field, 'typed');
  await userEvent.click(elsewhere);

  // `saved` is still empty: the request is in flight. Leaving the untouched
  // field again would create a second record.
  await userEvent.click(field);
  await userEvent.click(elsewhere);

  expect(onCommit).toHaveBeenCalledExactlyOnceWith('typed');
});

test('Enter commits once, Escape reverts without committing', async () => {
  const { onCommit, field, elsewhere } = await renderProbe('saved text');

  await userEvent.fill(field, 'changed');
  await userEvent.keyboard('{Enter}');
  expect(onCommit).toHaveBeenCalledExactlyOnceWith('changed');

  await userEvent.fill(field, 'discarded');
  await userEvent.keyboard('{Escape}');
  await expect.element(field).toHaveValue('saved text');

  // The blur that follows Escape must not save the reverted text either.
  await userEvent.click(elsewhere);
  expect(onCommit).toHaveBeenCalledExactlyOnceWith('changed');
});
