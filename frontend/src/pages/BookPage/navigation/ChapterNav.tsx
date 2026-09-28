import { Collapsable } from '@/components/animations/Collapsable.tsx';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { ChapterListIcon } from '@/theme/Icons.tsx';
import { Box, Button, Typography } from '@mui/material';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { SidebarSectionHeader } from './SidebarSectionHeader.tsx';

export interface ChapterNavigationData {
  id: number;
  name: string;
  highlightCount: number;
  flashcardCount: number;
}

interface ChapterNavProps {
  chapters: ChapterNavigationData[];
  onChapterClick: (chapterId: number) => void;
  hideTitle?: boolean;
}

export const ChapterNav = ({ chapters, onChapterClick, hideTitle }: ChapterNavProps) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(() => true);
  const chaptersId = useId();
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
        <SidebarSectionHeader
          icon={ChapterListIcon}
          title={t('common.entities.chapters')}
          collapse={{
            isExpanded,
            onToggle: () => setIsExpanded((prev) => !prev),
            sectionLabel: t('book.navigation.chapters.sectionLabel'),
            controlsId: chaptersId,
          }}
        />
      )}

      <Collapsable isExpanded={effectiveIsExpanded}>
        <Box
          id={chaptersId}
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
          aria-label={t('common.entities.chapters')}
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
                  <MetadataRow
                    variant="caption"
                    // Counts are omitted at zero, so a chapter reads the same on
                    // whichever tab lists it.
                    items={[
                      chapter.highlightCount > 0
                        ? t('common.counts.highlights', { count: chapter.highlightCount })
                        : null,
                      chapter.flashcardCount > 0
                        ? t('common.counts.flashcards', { count: chapter.flashcardCount })
                        : null,
                    ]}
                    sx={{ fontSize: '0.75rem', mt: 0.25, display: 'block' }}
                  />
                </Box>
              </Button>
            </Box>
          ))}
        </Box>
      </Collapsable>
    </Box>
  );
};
