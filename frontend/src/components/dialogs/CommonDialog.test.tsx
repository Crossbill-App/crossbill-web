import { CommonDialog } from '@/components/dialogs/CommonDialog';
import { theme } from '@/theme/theme';
import { ThemeProvider } from '@mui/material/styles';
import { afterEach, expect, test, vi } from 'vitest';
import { render } from 'vitest-browser-react';
import { page, userEvent } from 'vitest/browser';

/** The suite's own viewport, restored so a resize here can't leak sideways. */
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };

afterEach(async () => {
  await page.viewport(DESKTOP.width, DESKTOP.height);
});

const renderDialog = (props: Partial<Parameters<typeof CommonDialog>[0]> = {}) =>
  render(
    <ThemeProvider theme={theme}>
      <CommonDialog open onClose={vi.fn()} title="Chapter three" {...props}>
        <p>Body</p>
      </CommonDialog>
    </ThemeProvider>
  );

const aNavigation = (overrides = {}) => ({
  hasPrevious: true,
  hasNext: true,
  onPrevious: vi.fn(),
  onNext: vi.fn(),
  ...overrides,
});

test.for([
  ['a phone', PHONE],
  ['a wide screen', DESKTOP],
] as const)('%s pages between entities from arrows in the footer', async ([, viewport]) => {
  await page.viewport(viewport.width, viewport.height);
  const navigation = aNavigation();
  const screen = await renderDialog({ navigation });

  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(navigation.onNext).toHaveBeenCalled();

  await userEvent.click(screen.getByRole('button', { name: 'Previous' }));
  expect(navigation.onPrevious).toHaveBeenCalled();
});

test('an end of the list retires its arrow rather than hiding it', async () => {
  await page.viewport(PHONE.width, PHONE.height);
  const screen = await renderDialog({ navigation: aNavigation({ hasPrevious: false }) });

  await expect.element(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  await expect.element(screen.getByRole('button', { name: 'Next' })).toBeEnabled();
});

/**
 * The footer is the one place paging is always available, so it carries the
 * arrows even for a dialog that has no actions of its own to put beside them.
 */
test('navigation alone is enough to render the footer', async () => {
  const screen = await renderDialog({ navigation: aNavigation() });

  await expect.element(screen.getByRole('button', { name: 'Next' })).toBeVisible();
});

test('a dialog with neither actions nor navigation renders no footer at all', async () => {
  const screen = await renderDialog();

  expect(screen.getByRole('button', { name: 'Next' }).elements()).toHaveLength(0);
  expect(screen.getByRole('button', { name: 'Previous' }).elements()).toHaveLength(0);
});

test('footer actions sit alongside the arrows', async () => {
  const screen = await renderDialog({
    navigation: aNavigation(),
    footerActions: <button type="button">Save</button>,
  });

  await expect.element(screen.getByRole('button', { name: 'Save' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Next' })).toBeVisible();
});
