import type { ContentType, SemanticSearchResults } from '@/api/generated/model';
import { useRelatedContent } from '@/api/generated/semantic/semantic.ts';
import { strongEnough } from '@/components/search/semanticScore.ts';
import { useSettings } from '@/context/SettingsContext.tsx';
import { useMemo } from 'react';

interface UseRelatedItemsOptions {
  contentType: ContentType;
  contentId: number | undefined;
  limit?: number;
}

interface RelatedItemsState {
  related: SemanticSearchResults | undefined;
  isFetching: boolean;
  isError: boolean;
  isEnabled: boolean;
}

/** Per content type, which is also as many as a related strip renders. */
const DEFAULT_LIMIT = 10;
const MIN_SCORE = 0.6;

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

  const results = useMemo(() => {
    if (!isEnabled || !data) return undefined;
    return {
      highlights: strongEnough(data.highlights, MIN_SCORE),
      notes: strongEnough(data.notes, MIN_SCORE),
      digests: strongEnough(data.digests, MIN_SCORE),
    };
  }, [data, isEnabled]);

  return { related: results, isFetching, isError, isEnabled };
};
