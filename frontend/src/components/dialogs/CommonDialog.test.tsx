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
] as const)('%s pages between entities from its arrows', async ([, viewport]) => {
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

/** Paging does not depend on the dialog having actions of its own. */
test('navigation alone is enough to render the arrows', async () => {
  const screen = await renderDialog({ navigation: aNavigation() });

  await expect.element(screen.getByRole('button', { name: 'Next' })).toBeVisible();
});

/**
 * The pair beside the content and the pair in the footer are alternatives, not
 * a set: both used to render from `sm` up, so a tablet carried four arrow
 * buttons for two actions.
 */
test.for([
  ['a phone', PHONE],
  ['a wide screen', DESKTOP],
] as const)('%s shows one pair of arrows, not two', async ([, viewport]) => {
  await page.viewport(viewport.width, viewport.height);
  const screen = await renderDialog({ navigation: aNavigation() });

  await expect.element(screen.getByRole('button', { name: 'Next' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Next' }).elements()).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Previous' }).elements()).toHaveLength(1);
});

test('a dialog with neither actions nor navigation renders no footer at all', async () => {
  const screen = await renderDialog();

  expect(screen.getByRole('button', { name: 'Next' }).elements()).toHaveLength(0);
  expect(screen.getByRole('button', { name: 'Previous' }).elements()).toHaveLength(0);
});

test('footer actions sit alongside the arrows on a phone', async () => {
  await page.viewport(PHONE.width, PHONE.height);
  const screen = await renderDialog({
    navigation: aNavigation(),
    footerActions: <button type="button">Save</button>,
  });

  await expect.element(screen.getByRole('button', { name: 'Save' })).toBeVisible();
  await expect.element(screen.getByRole('button', { name: 'Next' })).toBeVisible();
});

/**
 * Regression for #621: a nested dialog's own lock/unlock must not clobber
 * the outer dialog's scroll lock while the outer dialog is still open.
 */
test('closing a nested dialog leaves the outer dialog body scroll lock intact', async () => {
  await renderDialog();
  const lockedTop = document.body.style.top;
  expect(document.body.style.position).toBe('fixed');

  const nested = await render(
    <ThemeProvider theme={theme}>
      <CommonDialog open onClose={vi.fn()} title="Nested">
        <p>Nested body</p>
      </CommonDialog>
    </ThemeProvider>
  );
  await expect.element(nested.getByText('Nested body')).toBeVisible();

  await nested.unmount();

  expect(document.body.style.position).toBe('fixed');
  expect(document.body.style.top).toBe(lockedTop);
});

/**
 * Regression for #620: registration on the dialog stack lives in the shell,
 * so a nested dialog shadows the one beneath it without its own author having
 * to opt in.
 */
test('a nested dialog with no navigation of its own blocks arrow keys from the dialog beneath it', async () => {
  const navigation = aNavigation();
  await renderDialog({ navigation });

  const nested = await renderDialog({ title: 'Nested' });
  await expect.element(nested.getByText('Nested')).toBeVisible();

  await userEvent.keyboard('{ArrowRight}');

  expect(navigation.onNext).not.toHaveBeenCalled();
});

test('closing the nested dialog restores arrow-key paging on the dialog beneath it', async () => {
  const navigation = aNavigation();
  await renderDialog({ navigation });
  const nested = await renderDialog({ title: 'Nested' });

  await nested.unmount();
  await userEvent.keyboard('{ArrowRight}');

  expect(navigation.onNext).toHaveBeenCalled();
});

test('arrow keys page the dialog and stop at the ends of the list', async () => {
  const navigation = aNavigation({ hasNext: false });
  await renderDialog({ navigation });

  await userEvent.keyboard('{ArrowRight}');
  expect(navigation.onNext).not.toHaveBeenCalled();

  await userEvent.keyboard('{ArrowLeft}');
  expect(navigation.onPrevious).toHaveBeenCalled();
});
