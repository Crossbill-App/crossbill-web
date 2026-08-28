import { FilterListIcon } from '@/theme/Icons';
import { Box, Chip } from '@mui/material';

import { theme } from '@/theme/theme.ts';
import { filterChipSx } from '../../navigation/filterChipStyles.ts';
import { SidebarSectionHeader } from '../../navigation/SidebarSectionHeader';
import { NOTE_KINDS, NOTE_KIND_LABELS, type NoteKindValue } from '../noteKinds';

interface NoteKindFilterProps {
  selected: NoteKindValue[];
  onChange: (next: NoteKindValue[]) => void;
  hideTitle?: boolean;
}

export const NoteKindFilter = ({ selected, onChange, hideTitle = false }: NoteKindFilterProps) => {
  const toggle = (kind: NoteKindValue) => {
    onChange(selected.includes(kind) ? selected.filter((k) => k !== kind) : [...selected, kind]);
  };

  return (
    <Box>
      {!hideTitle && <SidebarSectionHeader icon={FilterListIcon} title="Note types" />}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 1,
          mt: 2,
          mb: 2,
          [theme.breakpoints.down('md')]: {
            flexDirection: 'column',
          },
        }}
      >
        {NOTE_KINDS.map((kind) => {
          const active = selected.includes(kind);
          return (
            <Chip
              key={kind}
              label={NOTE_KIND_LABELS[kind]}
              size="small"
              color={active ? 'primary' : 'default'}
              variant={active ? 'filled' : 'outlined'}
              onClick={() => toggle(kind)}
              sx={filterChipSx(active)}
            />
          );
        })}
      </Box>
    </Box>
  );
};
