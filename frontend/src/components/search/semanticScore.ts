/**
 * Cosine-similarity floor for a result worth showing.
 *
 * Nearest-neighbour search always returns its top N, so a query with no real
 * match still comes back with the least-bad items. Without a floor, "quantum"
 * against a philosophy book produces a confident-looking list of noise. 0.35 is
 * a starting value for this embedding model, not a measured one.
 */
const MIN_SCORE = 0.35;

export const strongEnough = <T extends { score: number }>(items: T[], minScore = MIN_SCORE) =>
  items.filter((item) => item.score >= minScore);
