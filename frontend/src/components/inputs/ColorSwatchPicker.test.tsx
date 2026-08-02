import { ColorSwatchPicker } from '@/components/inputs/ColorSwatchPicker';
import type { ColorOption } from '@/utils/colorUtils';
import { expect, test, vi } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

const COLORS: ColorOption[] = [
  { value: '#F59E0B', name: 'Yellow' },
  { value: '#3B82F6', name: 'Blue' },
];

test('renders a swatch per color', async () => {
  const screen = await render(
    <ColorSwatchPicker colors={COLORS} onChange={vi.fn()} label="Label color" />
  );

  await expect.element(screen.getByRole('button', { name: 'Yellow' })).toBeInTheDocument();
  await expect.element(screen.getByRole('button', { name: 'Blue' })).toBeInTheDocument();
});

test('reports the selected color to assistive tech', async () => {
  const screen = await render(
    <ColorSwatchPicker colors={COLORS} value="#3B82F6" onChange={vi.fn()} label="Label color" />
  );

  await expect
    .element(screen.getByRole('button', { name: 'Blue' }))
    .toHaveAttribute('aria-pressed', 'true');
  await expect
    .element(screen.getByRole('button', { name: 'Yellow' }))
    .toHaveAttribute('aria-pressed', 'false');
});

test('matches the selected color regardless of hex casing', async () => {
  const screen = await render(
    <ColorSwatchPicker colors={COLORS} value="#3b82f6" onChange={vi.fn()} label="Label color" />
  );

  await expect
    .element(screen.getByRole('button', { name: 'Blue' }))
    .toHaveAttribute('aria-pressed', 'true');
});

test('emits the hex value of the clicked swatch', async () => {
  const onChange = vi.fn();
  const screen = await render(
    <ColorSwatchPicker colors={COLORS} value="#F59E0B" onChange={onChange} label="Label color" />
  );

  await userEvent.click(screen.getByRole('button', { name: 'Blue' }));

  expect(onChange).toHaveBeenCalledExactlyOnceWith('#3B82F6');
});
