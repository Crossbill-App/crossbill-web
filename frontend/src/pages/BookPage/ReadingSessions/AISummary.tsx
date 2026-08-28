import { Collapsable } from '@/components/animations/Collapsable';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import { CollapseChevron } from '@/components/CollapseChevron.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { markdownStyles } from '@/theme/theme';
import { Box, styled } from '@mui/material';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface AISummaryProps {
  summary?: string | null;
}

const PreviewContent = styled(Box)(({ theme }) => ({
  display: '-webkit-box',
  WebkitLineClamp: 3,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  ...markdownStyles(theme),
}));

const ExpandedContent = styled(Box)(({ theme }) => ({
  ...markdownStyles(theme),
}));

export const AISummary = ({ summary }: AISummaryProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!summary) {
    return null;
  }

  return (
    <HoverableCardActionArea
      onClick={() => setIsExpanded(!isExpanded)}
      aria-expanded={isExpanded}
      aria-label={isExpanded ? 'Hide summary' : 'Show full summary'}
      sx={(theme) => ({
        padding: theme.spacing(1.5, 2),
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1,
      })}
    >
      <Box sx={{ flex: 1, minWidth: 0, pointerEvents: 'none' }}>
        {!isExpanded && (
          <PreviewContent>
            <ReactMarkdown>{summary}</ReactMarkdown>
          </PreviewContent>
        )}

        <Collapsable isExpanded={isExpanded}>
          <ExpandedContent>
            <ReactMarkdown>{summary}</ReactMarkdown>
          </ExpandedContent>
        </Collapsable>
      </Box>
      <CollapseChevron
        isExpanded={isExpanded}
        sx={{ fontSize: ICON_SIZE.ui, color: 'text.secondary', flexShrink: 0, mt: 0.25 }}
      />
    </HoverableCardActionArea>
  );
};
