import { PAGE_GUTTER, PageContainer } from '@/components/layout/Layouts';
import { theme } from '@/theme/theme';
import { ThemeProvider } from '@mui/material/styles';
import { expect, test } from 'vitest';
import { render } from 'vitest-browser-react';
import { page } from 'vitest/browser';

/**
 * A full-bleed carousel cancels PAGE_GUTTER to reach the screen edge, so the
 * constant has to be what PageContainer actually applies — not just a value
 * that happens to look right.
 */
test.each([
  ['xs', 400, PAGE_GUTTER.xs],
  ['sm', 900, PAGE_GUTTER.sm],
])('PageContainer pads by PAGE_GUTTER at %s', async (_name, width, spacing) => {
  await page.viewport(width, 700);
  await render(
    <ThemeProvider theme={theme}>
      <PageContainer maxWidth="xl" data-gutter-probe="">
        content
      </PageContainer>
    </ThemeProvider>
  );

  const style = getComputedStyle(document.querySelector<HTMLElement>('[data-gutter-probe]')!);
  expect([style.paddingLeft, style.paddingRight]).toEqual([
    theme.spacing(spacing),
    theme.spacing(spacing),
  ]);
});
