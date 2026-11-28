import { describe, expect, test } from 'vitest';
import { reviewInterval } from './reviewInterval';

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

describe('reviewInterval', () => {
  test.each([
    [0, { unit: 'minutes', count: 1 }],
    [-5 * MINUTE, { unit: 'minutes', count: 1 }],
    [10 * MINUTE, { unit: 'minutes', count: 10 }],
    [59.6 * MINUTE, { unit: 'hours', count: 1 }],
    [8 * HOUR, { unit: 'hours', count: 8 }],
    [23.6 * HOUR, { unit: 'days', count: 1 }],
    [3 * DAY, { unit: 'days', count: 3 }],
    [29.6 * DAY, { unit: 'months', count: 1 }],
    [75 * DAY, { unit: 'months', count: 3 }],
    [359 * DAY, { unit: 'years', count: 1 }],
    [548 * DAY, { unit: 'years', count: 1.5 }],
  ])('%d ms reads as %o', (milliseconds, expected) => {
    expect(reviewInterval(milliseconds)).toEqual(expected);
  });
});
