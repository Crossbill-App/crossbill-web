import { FilterListIcon } from '@/theme/Icons';
import { Box, Chip } from '@mui/material';
import { useTranslation } from 'react-i18next';

import { theme } from '@/theme/theme.ts';
import { SidebarSectionHeader } from '../../navigation/SidebarSectionHeader';
import { NOTE_KINDS, type NoteKindValue } from '../noteKinds';

interface NoteKindFilterProps {
  selected: NoteKindValue[];
  onChange: (next: NoteKindValue[]) => void;
  hideTitle?: boolean;
}

export const NoteKindFilter = ({ selected, onChange, hideTitle = false }: NoteKindFilterProps) => {
  const { t } = useTranslation();
  const toggle = (kind: NoteKindValue) => {
    onChange(selected.includes(kind) ? selected.filter((k) => k !== kind) : [...selected, kind]);
  };

  return (
    <Box>
      {!hideTitle && <SidebarSectionHeader icon={FilterListIcon} title={t('notes.shared.types')} />}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 1,
          mt: 1,
          mb: 4.5,
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
              label={t(`notes.kinds.${kind}`)}
              color={active ? 'primary' : 'default'}
              variant={active ? 'filled' : 'outlined'}
              onClick={() => toggle(kind)}
            />
          );
        })}
      </Box>
    </Box>
  );
};
