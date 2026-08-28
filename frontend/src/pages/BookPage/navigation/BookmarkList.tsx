import type { Bookmark, Highlight } from '@/api/generated/model';
import { Collapsable } from '@/components/animations/Collapsable.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { BookmarkFilledIcon } from '@/theme/Icons.tsx';
import { Box, Button, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { SidebarSectionHeader } from './SidebarSectionHeader.tsx';

interface BookmarkListProps {
  bookmarks: Bookmark[];
  allHighlights: Highlight[];
  onBookmarkClick: (highlightId: number) => void;
  hideTitle?: boolean;
  filterActive?: boolean;
}

export const BookmarkList = ({
  bookmarks,
  allHighlights,
  onBookmarkClick,
  hideTitle,
  filterActive = false,
}: BookmarkListProps) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const bookmarksId = useId();
  const effectiveIsExpanded = hideTitle ? true : isExpanded;

  // Create a map of highlight IDs to highlights for quick lookup
  const highlightMap = new Map(allHighlights.map((h) => [h.id, h]));

  // Get highlights for bookmarks and sort by page number
  const bookmarkedHighlights =
    bookmarks.length > 0
      ? bookmarks
          .map((bookmark) => ({
            bookmark,
            highlight: highlightMap.get(bookmark.highlight_id),
          }))
          .filter((item) => item.highlight !== undefined)
          .sort((a, b) => {
            const pageA = a.highlight?.page ?? Infinity;
            const pageB = b.highlight?.page ?? Infinity;
            return pageA - pageB;
          })
      : [];

  // Truncate highlight text to first few words
  const truncateText = (text: string, wordCount: number = 5): string => {
    const words = text.split(/\s+/);
    if (words.length <= wordCount) {
      return text;
    }
    return words.slice(0, wordCount).join(' ') + '...';
  };

  return (
    <Box
      sx={{
        flex: '1 1 auto',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {!hideTitle && (
        <SidebarSectionHeader
          icon={BookmarkFilledIcon}
          title="Bookmarks"
          collapse={{
            isExpanded,
            onToggle: () => setIsExpanded((prev) => !prev),
            sectionLabel: 'bookmark list',
            controlsId: bookmarksId,
          }}
        />
      )}

      <Collapsable isExpanded={effectiveIsExpanded}>
        {bookmarkedHighlights.length > 0 ? (
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
            aria-label="Bookmarks"
          >
            {bookmarkedHighlights.map(({ bookmark, highlight }) => {
              if (!highlight) return null;

              const startsWithLowercase =
                highlight.text.length > 0 &&
                highlight.text[0] === highlight.text[0].toLowerCase() &&
                highlight.text[0] !== highlight.text[0].toUpperCase();

              const prefix = startsWithLowercase ? '...' : '';
              const truncatedText = prefix + truncateText(highlight.text);

              return (
                <Box component="li" key={bookmark.id}>
                  <Button
                    fullWidth
                    disableRipple
                    onClick={() => onBookmarkClick(highlight.id)}
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
                        {truncatedText}
                      </Typography>
                      {highlight.page && (
                        <Typography
                          variant="caption"
                          sx={{
                            color: 'text.secondary',
                            fontSize: '0.75rem',
                            mt: 0.25,
                            display: 'block',
                          }}
                        >
                          Page {highlight.page}
                        </Typography>
                      )}
                    </Box>
                  </Button>
                </Box>
              );
            })}
          </Box>
        ) : (
          <EmptyStateText>
            {filterActive ? 'No bookmarks match the active filters.' : 'No bookmarks yet.'}
          </EmptyStateText>
        )}
      </Collapsable>
    </Box>
  );
};
