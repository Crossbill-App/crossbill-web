import { useGetBookHighlightLabels } from '@/api/generated/highlight-labels/highlight-labels.ts';
import type { HighlightLabelInBook } from '@/api/generated/model';
import { LabelChip } from '@/components/highlights/LabelChip.tsx';
import { EditIcon, PaletteIcon } from '@/theme/Icons.tsx';
import { DEFAULT_LABEL_COLOR } from '@/utils/colorUtils.ts';
import { Box, Button } from '@mui/material';
import { useState } from 'react';

import { HighlightLabelsDialog } from './HighlightLabelsDialog.tsx';
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
  return label.ui_color || DEFAULT_LABEL_COLOR;
};

export const HighlightLabelsList = ({
  bookId,
  selectedLabelId,
  onLabelClick,
  hideTitle,
}: HighlightLabelsListProps) => {
  const { data } = useGetBookHighlightLabels(bookId);
  const [isEditing, setIsEditing] = useState(false);
  const labels = data?.items;

  // Shown from one label up. Hiding the section below two meant a reader whose
  // highlights are all one colour never learned labels can be named or
  // recoloured at all.
  if (!labels || labels.length === 0) {
    return null;
  }

  const editButton = (
    <Button size="small" startIcon={<EditIcon />} onClick={() => setIsEditing(true)}>
      Edit labels
    </Button>
  );

  return (
    <Box>
      {hideTitle ? (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>{editButton}</Box>
      ) : (
        <SidebarSectionHeader icon={PaletteIcon} title="Labels" action={editButton} />
      )}

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
        {labels.map((label) => (
          <LabelChip
            key={label.id}
            name={getLabelDisplayName(label)}
            color={getLabelColor(label)}
            count={label.highlight_count}
            isSelected={selectedLabelId === label.id}
            onClick={() => onLabelClick(selectedLabelId === label.id ? null : label.id)}
          />
        ))}
      </Box>

      <HighlightLabelsDialog bookId={bookId} open={isEditing} onClose={() => setIsEditing(false)} />
    </Box>
  );
};
