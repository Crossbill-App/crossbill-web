import type { ContentType } from '@/api/generated/model';
import { useRelatedContent } from '@/api/generated/semantic/semantic.ts';
import { mergeSearchRows, type GlobalSearchRow } from '@/components/search/globalSearchRows.ts';
import { useSettings } from '@/context/SettingsContext.tsx';
import { useMemo } from 'react';

interface UseRelatedItemsOptions {
  contentType: ContentType;
  contentId: number | undefined;
  limit?: number;
}

interface RelatedItemsState {
  /** One ranking across all three content types, best match first. */
  rows: GlobalSearchRow[];
  isFetching: boolean;
  isError: boolean;
  isEnabled: boolean;
}

/**
 * Per content type on the way in, and the length of the merged strip on the
 * way out — the endpoint ranks each type separately, so asking for ten of each
 * is what makes a merged top ten able to draw on all three.
 */
const DEFAULT_LIMIT = 10;

/**
 * Content semantically related to one anchor, as a single ranked list.
 *
 * One list rather than a strip per content type: cosine similarity is one
 * scale for highlights, notes and digests, so the best matches for an anchor
 * are simply the best matches. Splitting them by type also gave each type its
 * own floor to clear, which emptied the note strip on most anchors while the
 * merged page it belonged in was full.
 *
 * Weak matches never arrive — the endpoint holds the floor — so an empty
 * `rows` means the anchor has no strong neighbours, not that filtering ate
 * them.
 */
export const useRelatedItems = ({
  contentType,
  contentId,
  limit = DEFAULT_LIMIT,
}: UseRelatedItemsOptions): RelatedItemsState => {
  const { featureFlags } = useSettings();
  // An absent anchor is as disabling as the flag: there is nothing to be
  // related to, and `content_id` is required, so the request cannot be honest.
  const isEnabled = featureFlags?.embeddings === true && contentId !== undefined;

  const { data, isFetching, isError } = useRelatedContent(
    {
      content_id: contentId ?? 0,
      content_type: contentType,
      limit,
    },
    {
      query: { enabled: isEnabled },
    }
  );

  const rows = useMemo(
    () => (isEnabled ? mergeSearchRows(data).slice(0, limit) : []),
    [data, isEnabled, limit]
  );

  return { rows, isFetching, isError, isEnabled };
};
