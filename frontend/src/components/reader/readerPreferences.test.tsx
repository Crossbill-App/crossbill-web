import {
  DEFAULT_READER_PREFERENCES,
  READER_SPACINGS,
  toEbookAppearance,
} from '@/components/reader/readerPreferences.ts';
import { theme } from '@/theme/theme.ts';
import {
  lineHeightRangeConfig,
  paragraphIndentRangeConfig,
  paragraphSpacingRangeConfig,
} from '@readium/navigator';
import { expect, test } from 'vitest';

// The spacings are ours rather than the engine's, so nothing but this notices
// an upgrade that narrows a range out from under them.
test('every spacing the reader is offered is one the engine honours', () => {
  for (const spacing of READER_SPACINGS) {
    const appearance = toEbookAppearance(theme, { ...DEFAULT_READER_PREFERENCES, spacing });
    const sent: [number | null, [number, number]][] = [
      [appearance.lineHeight, lineHeightRangeConfig.range],
      [appearance.paragraphSpacing, paragraphSpacingRangeConfig.range],
      [appearance.paragraphIndent, paragraphIndentRangeConfig.range],
    ];

    for (const [value, [min, max]] of sent) {
      if (value === null) continue;
      expect(value).toBeGreaterThanOrEqual(min);
      expect(value).toBeLessThanOrEqual(max);
    }
  }
});
