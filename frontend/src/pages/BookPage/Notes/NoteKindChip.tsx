import { Chip, type ChipProps } from '@mui/material';
import { NOTE_KIND_LABELS, noteKindOf } from './noteKinds';

interface NoteKindChipProps {
  /** The note's raw `kind`; anything unrecognised reads as "Other". */
  kind: string | null | undefined;
  sx?: ChipProps['sx'];
}

/** A note's type, wherever it is shown. Renders nothing for an untyped note. */
export const NoteKindChip = ({ kind, sx }: NoteKindChipProps) =>
  kind ? <Chip size="small" label={NOTE_KIND_LABELS[noteKindOf(kind)]} sx={sx} /> : null;
