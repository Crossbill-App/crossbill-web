export const getContrastColor = (hexColor: string): string => {
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? '#000000' : '#FFFFFF';
};

/** A selectable color: the hex value that gets stored, plus its display name. */
export interface ColorOption {
  /** Hex value persisted on the entity, e.g. `#F59E0B`. */
  value: string;
  /** Human-readable name, used as the accessible label of a swatch. */
  name: string;
}

/**
 * What a highlight is shown in when its label carries no colour of its own.
 *
 * The Gray of the palette below rather than a colour outside it: an unlabelled
 * highlight is still one of this set, just the quietest member. Named here so
 * the sidebar's label chips and the web reader's decorations agree on it.
 */
export const DEFAULT_LABEL_COLOR = '#6B7280';

export const LABEL_COLORS: readonly ColorOption[] = [
  { value: '#F59E0B', name: 'Yellow' }, // KOReader
  { value: '#F97316', name: 'Orange' }, // KOReader
  { value: '#EF4444', name: 'Red' }, // KOReader
  { value: '#EC4899', name: 'Pink' },
  { value: '#8B5CF6', name: 'Purple' }, // KOReader
  { value: '#6366F1', name: 'Indigo' },
  { value: '#3B82F6', name: 'Blue' }, // KOReader
  { value: '#06B6D4', name: 'Cyan' }, // KOReader
  { value: '#14B8A6', name: 'Teal' },
  { value: '#10B981', name: 'Green' }, // KOReader
  { value: '#84CC16', name: 'Olive' }, // KOReader
  { value: '#059669', name: 'Emerald' },
  { value: DEFAULT_LABEL_COLOR, name: 'Gray' }, // KOReader
  { value: '#475569', name: 'Slate' },
];
