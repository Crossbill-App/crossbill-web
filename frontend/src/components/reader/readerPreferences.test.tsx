import {
  DEFAULT_READER_PREFERENCES,
  READER_LINE_HEIGHTS,
  toEbookAppearance,
} from '@/components/reader/readerPreferences.ts';
import { theme } from '@/theme/theme.ts';
import { lineHeightRangeConfig } from '@readium/navigator';
import { expect, test } from 'vitest';

// The line heights are ours rather than the engine's, so nothing but this
// notices an upgrade that narrows the range out from under them.
test('every line height the reader is offered is one the engine honours', () => {
  const [min, max] = lineHeightRangeConfig.range;

  for (const lineHeight of READER_LINE_HEIGHTS) {
    const { lineHeight: sent } = toEbookAppearance(theme, {
      ...DEFAULT_READER_PREFERENCES,
      lineHeight,
    });
    if (sent === null) continue;
    expect(sent).toBeGreaterThanOrEqual(min);
    expect(sent).toBeLessThanOrEqual(max);
  }
});
