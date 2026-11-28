export interface ReviewInterval {
  unit: 'minutes' | 'hours' | 'days' | 'months' | 'years';
  count: number;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** How long until a card would be due again, in the largest unit that keeps it a whole number. */
export const reviewInterval = (milliseconds: number): ReviewInterval => {
  const minutes = Math.max(1, Math.round(milliseconds / MINUTE));
  if (minutes < 60) return { unit: 'minutes', count: minutes };

  const hours = Math.round(milliseconds / HOUR);
  if (hours < 24) return { unit: 'hours', count: hours };

  const days = Math.round(milliseconds / DAY);
  if (days < 30) return { unit: 'days', count: days };

  const months = Math.round(milliseconds / (30 * DAY));
  if (months < 12) return { unit: 'months', count: months };

  return { unit: 'years', count: Math.round(milliseconds / (36.5 * DAY)) / 10 };
};
