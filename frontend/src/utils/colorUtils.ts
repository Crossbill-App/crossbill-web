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
  { value: '#6B7280', name: 'Gray' }, // KOReader
  { value: '#475569', name: 'Slate' },
];
