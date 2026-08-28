import { useGetBookHighlightLabels } from '@/api/generated/highlight-labels/highlight-labels.ts';
import type { HighlightLabelInBook } from '@/api/generated/model';
import { PaletteIcon } from '@/theme/Icons.tsx';
import { getContrastColor } from '@/utils/colorUtils.ts';
import { Box, Chip } from '@mui/material';

import { filterChipSx } from './filterChipStyles.ts';
import { SidebarSectionHeader } from './SidebarSectionHeader.tsx';

interface HighlightLabelsListProps {
  bookId: number;
  selectedLabelId?: number | null;
  onLabelClick: (labelId: number | null) => void;
  hideTitle?: boolean;
}

const getLabelDisplayName = (label: HighlightLabelInBook): string => {
  if (label.label) {
    return label.label;
  }
  const parts = [label.device_color, label.device_style].filter(Boolean);
  return parts.length > 0 ? parts.join(' / ') : 'Unlabeled';
};

const getLabelColor = (label: HighlightLabelInBook): string => {
  return label.ui_color || '#6B7280';
};

const LabelChip = ({
  label,
  isSelected,
  onClick,
}: {
  label: HighlightLabelInBook;
  isSelected: boolean;
  onClick: () => void;
}) => {
  const color = getLabelColor(label);
  const displayName = getLabelDisplayName(label);
  const chipLabel = `${displayName} (${label.highlight_count})`;

  return (
    <Chip
      label={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: color,
              flexShrink: 0,
            }}
          />
          <span>{chipLabel}</span>
        </Box>
      }
      size="small"
      variant={isSelected ? 'filled' : 'outlined'}
      onClick={onClick}
      sx={{
        ...filterChipSx(isSelected),
        // The one chip that keeps its own colour when selected: it is the
        // colour the highlight was made in on the device.
        ...(isSelected && {
          backgroundColor: color,
          color: getContrastColor(color),
          '&:hover': {
            backgroundColor: color,
            opacity: 0.85,
            transform: 'translateY(-1px)',
          },
        }),
      }}
    />
  );
};

export const HighlightLabelsList = ({
  bookId,
  selectedLabelId,
  onLabelClick,
  hideTitle,
}: HighlightLabelsListProps) => {
  const { data } = useGetBookHighlightLabels(bookId);
  const labels = data?.items;

  // Shown from one label up. Hiding the section below two meant a reader whose
  // highlights are all one colour never learned labels can be named or
  // recoloured — the editor is only reachable through the colour dot inside a
  // highlight dialog.
  if (!labels || labels.length === 0) {
    return null;
  }

  return (
    <Box>
      {!hideTitle && <SidebarSectionHeader icon={PaletteIcon} title="Labels" />}

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
        {labels.map((label) => (
          <LabelChip
            key={label.id}
            label={label}
            isSelected={selectedLabelId === label.id}
            onClick={() => onLabelClick(selectedLabelId === label.id ? null : label.id)}
          />
        ))}
      </Box>
    </Box>
  );
};
