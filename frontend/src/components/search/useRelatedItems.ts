import { ContentType, SemanticSearchResults } from '@/api/generated/model';
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

const DEFAULT_LIMIT = 25;
export const useRelatedItems = ({
  contentType,
  contentId,
  limit = DEFAULT_LIMIT,
}: UseRelatedItemsOptions): RelatedItemsState => {
  const { featureFlags } = useSettings();
  const embeddingsEnabled = !!featureFlags?.embeddings;

  const { data, isFetching, isError } = useRelatedContent(
    {
      content_id: contentId ?? 0,
      content_type: contentType,
      limit,
    },
    {
      query: { enabled: embeddingsEnabled },
    }
  );

  const results = useMemo(() => {
    if (!embeddingsEnabled || !data) return undefined;
    return {
      highlights: strongEnough(data.highlights),
      notes: strongEnough(data.notes),
      digests: strongEnough(data.digests),
    };
  }, [data, embeddingsEnabled]);
  return { related: results, isFetching, isError, isEnabled: embeddingsEnabled };
};
