import { describe, expect, it } from 'vitest';
import { formatSeconds } from './date.ts';

describe('formatSeconds', () => {
  it('says the hours and the minutes left over', () => {
    expect(formatSeconds(3600)).toBe('1h 0m');
    expect(formatSeconds(3 * 3600 + 25 * 60)).toBe('3h 25m');
  });

  it('drops the hours below the hour', () => {
    expect(formatSeconds(0)).toBe('0m');
    expect(formatSeconds(45 * 60)).toBe('45m');
  });

  // The minutes used to be rounded within the hour they belong to, so a second
  // short of a rollover produced "1h 60m" and "60m".
  it('carries a rounded-up minute into the next hour', () => {
    expect(formatSeconds(3599)).toBe('1h 0m');
    expect(formatSeconds(7199)).toBe('2h 0m');
  });

  it('rounds to the nearest minute either side of the half', () => {
    expect(formatSeconds(29)).toBe('0m');
    expect(formatSeconds(31)).toBe('1m');
    expect(formatSeconds(3569)).toBe('59m');
  });
});
