/**
 * Naming and recolouring the book's highlighters, from the Labels section.
 *
 * Both edits reach every highlight made with the highlighter, which is why they
 * live here rather than in the dialog of one highlight: there the swatches sat
 * under that highlight's own colour and were taken for it.
 */
import { aHighlightLabel, KOREADER_HUE } from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { highlightLabelApi } from '@tests/msw/highlightLabelApi';
import { expect, test } from 'vitest';
import { page, userEvent } from 'vitest/browser';

/**
 * The editor, scoped: an unnamed label wears its `yellow / lighten` name on the
 * sidebar chip behind the dialog too.
 */
const openTheLabelsEditor = async () => {
  const screen = await renderApp({ path: '/book/1/highlights' });
  await userEvent.click(screen.getByRole('button', { name: 'Edit labels' }).first());
  const dialog = page.getByRole('dialog');
  await expect.element(dialog.getByText('Highlight labels')).toBeVisible();
  return dialog;
};

test('a label row says how many highlights its name and colour reach', async () => {
  highlightLabelApi([aHighlightLabel({ highlight_count: 3 })]);

  const dialog = await openTheLabelsEditor();

  await expect.element(dialog.getByText('yellow / lighten')).toBeVisible();
  await expect.element(dialog.getByText('3 highlights')).toBeVisible();
});

test('recolouring a label writes the style, which is where that colour lives now', async () => {
  const { relabels } = highlightLabelApi([aHighlightLabel()]);

  await openTheLabelsEditor();
  await userEvent.click(
    page
      .getByRole('group', { name: 'Colour for yellow / lighten' })
      .getByRole('button', { name: 'Red' })
  );

  await expect.poll(() => relabels).toHaveLength(1);
  expect(relabels[0].url).toBe('/api/v1/highlight-labels/10');
  expect(relabels[0].body).toEqual({ ui_color: KOREADER_HUE.red });
});

test('naming a label writes the style it was typed under', async () => {
  const { relabels } = highlightLabelApi([
    aHighlightLabel({ id: 10, device_color: 'yellow' }),
    aHighlightLabel({
      id: 11,
      device_color: 'red',
      ui_color: KOREADER_HUE.red,
      highlight_count: 1,
    }),
  ]);

  await openTheLabelsEditor();
  await userEvent.fill(page.getByLabelText('Name for red / lighten'), 'Disagree');
  await userEvent.keyboard('{Enter}');

  await expect.poll(() => relabels).toHaveLength(1);
  expect(relabels[0].url).toBe('/api/v1/highlight-labels/11');
  expect(relabels[0].body).toEqual({ label: 'Disagree' });
});

/**
 * The swatch a label already wears is a toggle button, so the choice is
 * announced rather than left to the check mark alone — and it is matched
 * case-insensitively, because the API stores whatever hex string it was given
 * and KOReader's own hues arrive lower-case.
 */
test('the swatch a label already wears is announced as pressed, whatever the hex casing', async () => {
  highlightLabelApi([aHighlightLabel({ ui_color: KOREADER_HUE.yellow.toLowerCase() })]);

  await openTheLabelsEditor();
  const swatches = page.getByRole('group', { name: 'Colour for yellow / lighten' });

  await expect
    .element(swatches.getByRole('button', { name: 'Yellow' }))
    .toHaveAttribute('aria-pressed', 'true');
  await expect
    .element(swatches.getByRole('button', { name: 'Red' }))
    .toHaveAttribute('aria-pressed', 'false');
});
