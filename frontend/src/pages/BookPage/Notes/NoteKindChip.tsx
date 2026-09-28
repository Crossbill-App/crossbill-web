import { Chip, type ChipProps } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { noteKindOf } from './noteKinds';

interface NoteKindChipProps {
  /** The note's raw `kind`; anything unrecognised reads as "Other". */
  kind: string | null | undefined;
  sx?: ChipProps['sx'];
}

/** A note's type, wherever it is shown. Renders nothing for an untyped note. */
export const NoteKindChip = ({ kind, sx }: NoteKindChipProps) => {
  const { t } = useTranslation();
  return kind ? <Chip label={t(`notes.kinds.${noteKindOf(kind)}`)} sx={sx} /> : null;
};
