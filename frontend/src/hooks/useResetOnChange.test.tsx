import { useResetOnChange } from '@/hooks/useResetOnChange';
import { useState } from 'react';
import { expect, test } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

/** Mirrors `filter` into local state the way the book tabs mirror a URL param. */
const Probe = ({ filter }: { filter: string }) => {
  const [value, setValue] = useState(filter);
  useResetOnChange([filter], () => setValue(filter));

  return (
    <>
      <output>{value}</output>
      <button onClick={() => setValue('edited')}>edit</button>
    </>
  );
};

test('local edits survive re-renders until a dependency actually changes', async () => {
  const screen = await render(<Probe filter="alpha" />);
  await expect.element(screen.getByRole('status')).toHaveTextContent('alpha');

  await userEvent.click(screen.getByRole('button', { name: 'edit' }));
  await expect.element(screen.getByRole('status')).toHaveTextContent('edited');

  // Same dependency: the edit must stand. Resetting on every render instead of
  // on change would clobber it back to 'alpha' here.
  await screen.rerender(<Probe filter="alpha" />);
  await expect.element(screen.getByRole('status')).toHaveTextContent('edited');
});

test('a changed dependency re-initialises the state', async () => {
  const screen = await render(<Probe filter="alpha" />);
  await userEvent.click(screen.getByRole('button', { name: 'edit' }));
  await expect.element(screen.getByRole('status')).toHaveTextContent('edited');

  await screen.rerender(<Probe filter="beta" />);
  await expect.element(screen.getByRole('status')).toHaveTextContent('beta');
});
