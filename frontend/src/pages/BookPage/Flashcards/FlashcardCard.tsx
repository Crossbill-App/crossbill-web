import { Collapsable } from '@/components/animations/Collapsable';
import { CollapseChevron } from '@/components/CollapseChevron.tsx';
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
    position: 'relative',
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

const ActionButtonsStyled = styled(Box)(() => ({
  position: 'absolute',
  top: 8,
  right: 0,
  display: 'flex',
  gap: 0.5,
  zIndex: 1,
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
      <ButtonBase
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1,
          width: '100%',
          textAlign: 'left',
          pr: 8,
        }}
      >
        <Typography variant="body1" sx={{ flex: 1, lineHeight: 1.5 }}>
          {question}
        </Typography>
        <CollapseChevron
          isExpanded={isExpanded}
          sx={{ fontSize: 20, color: 'text.secondary', flexShrink: 0 }}
        />
      </ButtonBase>

      <Collapsable isExpanded={isExpanded}>
        <Box sx={{ mt: 1.5, pr: 8 }}>
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

      <ActionButtonsStyled>{renderActions()}</ActionButtonsStyled>
    </FlashcardStyled>
  );
};
