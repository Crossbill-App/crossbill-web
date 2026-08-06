import type { ReactNode } from 'react';
import { FeatureGate } from './FeatureGate.tsx';

interface EmbeddingFeatureProps {
  children: ReactNode;
}

export function EmbeddingFeature({ children }: EmbeddingFeatureProps) {
  return (
    <FeatureGate flag="embeddings" value={true}>
      {children}
    </FeatureGate>
  );
}
