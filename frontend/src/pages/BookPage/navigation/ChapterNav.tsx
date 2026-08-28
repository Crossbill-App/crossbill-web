import { Collapsable } from '@/components/animations/Collapsable.tsx';
import { CollapseChevron } from '@/components/CollapseChevron.tsx';
import { ChapterListIcon } from '@/theme/Icons.tsx';
import { Box, Button, IconButton, Typography } from '@mui/material';
import { useState } from 'react';

export interface ChapterNavigationData {
  id: number;
  name: string;
  itemCount: number;
}

interface ChapterNavProps {
  chapters: ChapterNavigationData[];
  onChapterClick: (chapterId: number) => void;
  hideTitle?: boolean;
  countType: 'highlight' | 'flashcard';
}

export const ChapterNav = ({ chapters, onChapterClick, hideTitle, countType }: ChapterNavProps) => {
  const [isExpanded, setIsExpanded] = useState(() => true);
  const effectiveIsExpanded = hideTitle ? true : isExpanded;

  if (chapters.length === 0) {
    return null;
  }

  return (
    <Box
      sx={{
        flex: '1 1 auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {!hideTitle && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 2,
            cursor: 'pointer',
            flexShrink: 0,
          }}
          onClick={() => setIsExpanded((prev) => !prev)}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ChapterListIcon sx={{ fontSize: 20, color: 'primary.main' }} />
            <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 600 }}>
              Chapters
            </Typography>
          </Box>
          <IconButton
            size="small"
            aria-label={isExpanded ? 'Collapse chapters list' : 'Expand chapters list'}
            sx={{ display: { xs: 'none', lg: 'block' } }}
          >
            <CollapseChevron isExpanded={isExpanded} sx={{ fontSize: 'small', display: 'block' }} />
          </IconButton>
        </Box>
      )}

      <Collapsable isExpanded={effectiveIsExpanded}>
        <Box
          component="ul"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
            flex: '1 1 auto',
            minHeight: 0,
            listStyle: 'none',
            p: 0,
            m: 0,
          }}
          aria-label="Chapters"
        >
          {chapters.map((chapter) => (
            <Box component="li" key={chapter.id}>
              <Button
                fullWidth
                disableRipple
                onClick={() => onChapterClick(chapter.id)}
                sx={{
                  display: 'flex',
                  alignItems: 'start',
                  justifyContent: 'flex-start',
                  textAlign: 'left',
                  gap: 1,
                  py: 0.75,
                  px: 0.5,
                  borderRadius: 0.5,
                  cursor: 'pointer',
                  transition: 'background-color 0.2s ease',
                  '@media (hover: hover)': {
                    '&:hover': {
                      bgcolor: 'action.hover',
                    },
                  },
                  '&:focus-visible': {
                    outline: '2px solid',
                    outlineOffset: '-2px',
                    outlineColor: 'primary.main',
                  },
                }}
              >
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    variant="body2"
                    sx={{
                      fontSize: '0.875rem',
                      color: 'text.primary',
                      lineHeight: 1.4,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {chapter.name}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      fontSize: '0.75rem',
                      mt: 0.25,
                      display: 'block',
                    }}
                  >
                    {chapter.itemCount} {countType === 'highlight' ? 'highlight' : 'flashcard'}
                    {chapter.itemCount !== 1 ? 's' : ''}
                  </Typography>
                </Box>
              </Button>
            </Box>
          ))}
        </Box>
      </Collapsable>
    </Box>
  );
};
