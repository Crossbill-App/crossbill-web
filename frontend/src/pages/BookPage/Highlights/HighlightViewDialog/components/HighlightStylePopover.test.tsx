/**
 * Recolouring one highlight, and naming the colour it wears.
 *
 * The two sit in the same popover and used to be the same edit: the only colour
 * control a stored highlight had was the label's, which every highlight of that
 * colour in the book shares — so making one passage red turned the rest of the
 * yellow ones red with it. The colour section now moves the highlight, the name
 * below it says whose name it is writing, and the label's own display colour is
 * not offered here at all (see `HighlightLabelsDialog`).
 */
import {
  aBookDetails,
  aChapter,
  aHighlight,
  aHighlightLabel,
  KOREADER_HUE,
} from '@tests/fixtures/book';
import { renderApp } from '@tests/harness/renderApp';
import { highlightLabelApi } from '@tests/msw/highlightLabelApi';
import { expect, test } from 'vitest';
import { page, userEvent } from 'vitest/browser';

const YELLOW_STYLE_ID = 10;

/** As the book reports a yellow highlight: unnamed, in KOReader's own hue. */
const asYellow = () => ({
  highlight_style_id: YELLOW_STYLE_ID,
  text: null,
  ui_color: KOREADER_HUE.yellow,
});

/** Two passages marked with the same highlighter; the reader opens the second. */
const aBookOfTwoYellowHighlights = () =>
  aBookDetails({
    chapters: [
      aChapter({
        id: 10,
        name: 'Chapter One',
        highlights: [
          aHighlight({ id: 300, text: 'The lantern went out', label: asYellow() }),
          aHighlight({ id: 301, text: 'Morning arrived without ceremony', label: asYellow() }),
        ],
      }),
    ],
  });

const RED_STYLE_ID = 11;

const aReaderOfTwoYellowHighlights = () =>
  highlightLabelApi(
    [
      aHighlightLabel({ id: YELLOW_STYLE_ID, highlight_count: 2 }),
      // Named, so moving a highlight into it turns the label's dot into a chip
      // -- the element the popover hangs off, replaced under it.
      aHighlightLabel({
        id: RED_STYLE_ID,
        device_color: 'red',
        ui_color: KOREADER_HUE.red,
        label: 'Disagree',
        highlight_count: 1,
      }),
    ],
    aBookOfTwoYellowHighlights()
  );

/** Where the open popover sits, as the reader sees it. */
const popoverRect = () => document.querySelector('.MuiPopover-paper')!.getBoundingClientRect();

/**
 * Whether the highlight's own label has become a named one.
 *
 * The dot is what an unnamed label renders as, and the element the popover is
 * anchored to; a named one is a chip instead, so the dot going is the swap
 * having happened. Read off the DOM rather than by role, because the popover is
 * a modal and everything under it -- the highlight's dialog included -- is
 * `aria-hidden` while it is up.
 */
const theLabelHasBecomeAChip = () =>
  document.querySelector('[aria-label="Change highlight colour"]') === null;

/** Where a swatch's name is showing, if it is showing anywhere but beside it. */
const strayTooltip = (): string | null => {
  const tip = document.querySelector('.MuiTooltip-popper');
  const swatch = document.querySelector('[aria-label="Red"]');
  if (!tip || !swatch) return null;
  const shown = tip.getBoundingClientRect();
  const names = swatch.getBoundingClientRect();
  const away = Math.hypot(shown.left - names.left, shown.top - names.top);
  return away > 80 ? `${Math.round(shown.left)},${Math.round(shown.top)}` : null;
};

/** Opens the second highlight and the style popover on its colour. */
const openTheStyleEditor = async () => {
  const screen = await renderApp({ path: '/book/1/highlights?highlightId=301' });
  const dialog = screen.getByRole('dialog');
  await expect.element(dialog.getByText('Morning arrived without ceremony')).toBeVisible();
  await userEvent.click(dialog.getByRole('button', { name: 'Change highlight colour' }));
  return screen;
};

const colourSection = () => page.getByRole('group', { name: 'Highlight colour' });

test('choosing another colour moves only the highlight it was opened on', async () => {
  const { recolours, relabels } = aReaderOfTwoYellowHighlights();

  await openTheStyleEditor();
  await userEvent.click(colourSection().getByRole('button', { name: 'Red' }));

  await expect.poll(() => recolours).toHaveLength(1);
  // The one highlight, by id -- not the style the other one shares with it.
  expect(recolours[0].url).toBe('/api/v1/books/1/highlights/301/color');
  expect(recolours[0].body).toEqual({ device_color: 'red', device_style: 'lighten' });
  expect(relabels).toHaveLength(0);
});

test('the colour a highlight already wears is not sent again', async () => {
  const { recolours } = aReaderOfTwoYellowHighlights();

  await openTheStyleEditor();
  await userEvent.click(colourSection().getByRole('button', { name: 'Yellow' }));

  await expect.element(page.getByPlaceholder('Label name...')).toBeVisible();
  expect(recolours).toHaveLength(0);
});

test('the label section names the colour it writes to', async () => {
  aReaderOfTwoYellowHighlights();

  await openTheStyleEditor();

  await expect.element(page.getByText('Label for Yellow')).toBeVisible();
});

test("naming the colour still writes the book's label for it, not the highlight", async () => {
  const { relabels, recolours } = aReaderOfTwoYellowHighlights();

  const screen = await openTheStyleEditor();
  await userEvent.fill(screen.getByPlaceholder('Label name...'), 'Disagree');
  await userEvent.keyboard('{Enter}');

  await expect.poll(() => relabels).toHaveLength(1);
  expect(relabels[0].url).toBe(`/api/v1/highlight-labels/${YELLOW_STYLE_ID}`);
  expect(relabels[0].body).toEqual({ label: 'Disagree' });
  expect(recolours).toHaveLength(0);
});

test("the only swatches here are the highlight's own colour", async () => {
  aReaderOfTwoYellowHighlights();

  await openTheStyleEditor();

  // One grid, not two: the second one was the label's display colour, and it
  // repainted the book's yellow highlights whenever it was taken for this one.
  await expect.element(colourSection()).toBeVisible();
  expect(page.getByRole('group', { name: 'Label colour' }).elements()).toHaveLength(0);
});

test('the popover follows the label it hangs off when the colour changes', async () => {
  aReaderOfTwoYellowHighlights();

  await openTheStyleEditor();
  const before = popoverRect();

  await userEvent.click(colourSection().getByRole('button', { name: 'Red' }));
  // Named, so the dot the popover was anchored to is now a chip.
  await expect.poll(theLabelHasBecomeAChip).toBe(true);

  // Still beside the label, give or take the couple of pixels between a dot and
  // the chip that replaced it -- not in the corner of the screen, which is where
  // measuring a detached node puts it.
  const after = popoverRect();
  expect(Math.abs(after.left - before.left)).toBeLessThan(40);
  expect(Math.abs(after.top - before.top)).toBeLessThan(40);
});

test('choosing a colour does not build the popover again', async () => {
  aReaderOfTwoYellowHighlights();

  const screen = await openTheStyleEditor();
  const field = screen.getByPlaceholder('Label name...').element();

  await userEvent.click(colourSection().getByRole('button', { name: 'Red' }));
  await expect.poll(theLabelHasBecomeAChip).toBe(true);

  // The same popover, carrying on -- not a second one raised over the first.
  expect(screen.getByPlaceholder('Label name...').element()).toBe(field);
});

test("a swatch's name is not left behind when the popover moves", async () => {
  aReaderOfTwoYellowHighlights();

  await openTheStyleEditor();
  const red = colourSection().getByRole('button', { name: 'Red' });
  await userEvent.hover(red);
  await expect.poll(() => document.querySelector('.MuiTooltip-popper') !== null).toBe(true);

  await userEvent.click(red);
  await expect.poll(theLabelHasBecomeAChip).toBe(true);

  // The popover moves to follow the chip that replaced the dot. A tooltip still
  // open across that move follows nothing, and strands itself mid-screen.
  expect(strayTooltip()).toBeNull();
});
