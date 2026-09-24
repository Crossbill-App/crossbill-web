import {
  loadReaderPreferences,
  READER_PREFERENCES_KEY,
} from '@/components/reader/preferences/readerPreferenceStorage.ts';
import {
  DEFAULT_READER_PREFERENCES,
  READER_SPACINGS,
  toEbookAppearance,
} from '@/components/reader/preferences/readerPreferences.ts';
import { theme } from '@/theme/theme.ts';
import {
  lineHeightRangeConfig,
  paragraphIndentRangeConfig,
  paragraphSpacingRangeConfig,
} from '@readium/navigator';
import { afterEach, expect, test, vi } from 'vitest';

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

afterEach(() => {
  vi.unstubAllGlobals();
});

const seedPreferences = (record: object) => {
  const stored = new Map([[READER_PREFERENCES_KEY, JSON.stringify(record)]]);
  const localStorage = { getItem: (key: string) => stored.get(key) ?? null };
  vi.stubGlobal('window', { localStorage });
};

test('a highlight colour no device offers is read as the default', () => {
  seedPreferences({ version: 1, highlightColor: 'chartreuse' });

  expect(loadReaderPreferences().highlightColor).toBe('yellow');
});
