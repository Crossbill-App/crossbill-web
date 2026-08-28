import { Collapsable } from '@/components/animations/Collapsable';
import { QuoteIcon } from '@/theme/Icons';
import { Box, ButtonBase, styled, Typography } from '@mui/material';
import { ReactNode, useState } from 'react';

export interface FlashcardCardProps {
  question: string;
  answer: string;
  showSourceHighlight?: boolean;
  sourceHighlightText?: string;
  renderActions: () => ReactNode;
  borderStyle?: 'solid' | 'dashed';
  borderColor?: 'primary' | 'grey';
}

const FlashcardStyled = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'borderStyle' && prop !== 'borderColor',
})<{ borderStyle?: 'solid' | 'dashed'; borderColor?: 'primary' | 'grey' }>(
  ({ theme, borderStyle = 'solid', borderColor = 'primary' }) => ({
    borderLeft: `3px ${borderStyle} ${borderColor === 'grey' ? theme.palette.divider : theme.palette.primary.main}`,
    paddingLeft: theme.spacing(2),
    paddingTop: theme.spacing(1),
    paddingBottom: theme.spacing(1),
    transition: 'background-color 0.15s ease',
    '&:hover': {
      backgroundColor: theme.palette.action.hover,
    },
  })
);

/**
 * In the flow beside the question rather than floating over it: the cluster is
 * three icons wide on the flashcards page, more than any fixed reserve on the
 * text would cover, so overlaying it meant covering the question on a narrow
 * row.
 */
const ActionButtonsStyled = styled(Box)(() => ({
  display: 'flex',
  flexShrink: 0,
  opacity: 0.7,
  transition: 'opacity 0.2s ease',
  '&:hover': {
    opacity: 1,
  },
}));

export const FlashcardCard = ({
  question,
  answer,
  showSourceHighlight,
  sourceHighlightText,
  renderActions,
  borderStyle = 'solid',
  borderColor = 'primary',
}: FlashcardCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <FlashcardStyled borderStyle={borderStyle} borderColor={borderColor}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
        <ButtonBase
          onClick={() => setIsExpanded(!isExpanded)}
          aria-expanded={isExpanded}
          sx={{
            display: 'block',
            flex: 1,
            minWidth: 0,
            textAlign: 'left',
          }}
        >
          <Typography variant="body1" sx={{ lineHeight: 1.5 }}>
            {question}
          </Typography>
        </ButtonBase>
        <ActionButtonsStyled>{renderActions()}</ActionButtonsStyled>
      </Box>

      <Collapsable isExpanded={isExpanded}>
        <Box sx={{ mt: 1.5 }}>
          <Typography
            variant="caption"
            sx={{
              color: 'secondary.main',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              display: 'block',
              mb: 0.5,
            }}
          >
            Answer
          </Typography>

          <Typography variant="body1" sx={{ color: 'text.secondary', lineHeight: 1.5 }}>
            {answer}
          </Typography>

          {/* Source highlight preview */}
          {showSourceHighlight && sourceHighlightText && (
            <Box
              sx={{
                mt: 2,
                pt: 2,
                borderTop: '1px dashed',
                borderColor: 'divider',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
                <QuoteIcon sx={{ fontSize: 14, color: 'text.disabled', mt: 0.25, flexShrink: 0 }} />
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.disabled',
                    fontStyle: 'italic',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    lineHeight: 1.4,
                  }}
                >
                  {sourceHighlightText}
                </Typography>
              </Box>
            </Box>
          )}
        </Box>
      </Collapsable>
    </FlashcardStyled>
  );
};
