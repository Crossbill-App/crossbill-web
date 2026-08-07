import type { ChapterWithHighlights, DigestSearchItem } from '@/api/generated/model';

interface ChapterMatches {
  /** Chapters to render: every match plus its ancestors, so the tree keeps its spine. */
  visibleIds: Set<number>;
  /** Best score on the chapter itself or any descendant — what the tree is ordered by. */
  bestScoreById: Map<number, number>;
}

/**
 * Turn matched digests into the chapters the structure tree should show.
 *
 * A digest matches one chapter, and showing that chapter alone would orphan it,
 * so each match walks up `parent_id` marking its ancestors visible and carrying
 * its score up with it.
 */
export const chapterMatchesFromDigests = (
  digests: DigestSearchItem[],
  chapters: ChapterWithHighlights[]
): ChapterMatches => {
  const parentById = new Map(chapters.map((chapter) => [chapter.id, chapter.parent_id ?? null]));
  const visibleIds = new Set<number>();
  const bestScoreById = new Map<number, number>();

  for (const digest of digests) {
    const seen = new Set<number>();
    let id: number | null = digest.chapter_id;
    while (id !== null && parentById.has(id) && !seen.has(id)) {
      seen.add(id);
      visibleIds.add(id);
      const best = bestScoreById.get(id);
      if (best === undefined || digest.score > best) {
        bestScoreById.set(id, digest.score);
      }
      id = parentById.get(id) ?? null;
    }
  }

  return { visibleIds, bestScoreById };
};
