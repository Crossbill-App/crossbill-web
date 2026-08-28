/**
 * A count and its unit: "1 bookmark", "2 bookmarks". Wherever a number is shown
 * with the thing it counts — the stats strip, the chapter rows, the chapter
 * sidebar — it goes through here rather than each site reinventing the plural.
 */
export const countLabel = (count: number, noun: string) =>
  `${count} ${noun}${count === 1 ? '' : 's'}`;
