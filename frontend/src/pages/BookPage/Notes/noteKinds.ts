export const NOTE_KINDS = ['character', 'term', 'concept', 'gist', 'reflection', 'other'] as const;

export type NoteKindValue = (typeof NOTE_KINDS)[number];

/** Kinds shown when the user hasn't set an explicit filter. Gists are excluded because they are usually very short. */
export const DEFAULT_NOTE_KINDS: NoteKindValue[] = NOTE_KINDS.filter((kind) => kind !== 'gist');

export const isNoteKind = (value: unknown): value is NoteKindValue =>
  NOTE_KINDS.includes(value as NoteKindValue);

/** The filter bucket a note falls into; untyped notes count as "other". */
export const noteKindOf = (kind: string | null | undefined): NoteKindValue =>
  isNoteKind(kind) ? kind : 'other';

export const isDefaultKindSelection = (kinds: NoteKindValue[]): boolean =>
  kinds.length === DEFAULT_NOTE_KINDS.length && DEFAULT_NOTE_KINDS.every((k) => kinds.includes(k));
