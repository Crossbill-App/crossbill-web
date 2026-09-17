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
  /** The name KOReader stores for this colour, on the nine colours it offers. */
  device_color?: string;
}

/** The colour of a highlight whose label names none, or none that can be drawn. */
export const DEFAULT_LABEL_COLOR = '#6B7280';

// The API stores any string, so a colour set by hand may lack its hash; anything
// else the engine would draw invisible, and it would still take a tap.
const HEX_COLOR = /^#?[0-9a-f]{6}$/i;

/** `color` as `#rrggbb` when the engine could draw it, else `fallback`. */
export const hexTint = (color: string | null | undefined, fallback: string): string =>
  color && HEX_COLOR.test(color) ? `#${color.replace('#', '')}` : fallback;

export const LABEL_COLORS: readonly ColorOption[] = [
  { value: '#F59E0B', name: 'Yellow', device_color: 'yellow' },
  { value: '#F97316', name: 'Orange', device_color: 'orange' },
  { value: '#EF4444', name: 'Red', device_color: 'red' },
  { value: '#EC4899', name: 'Pink' },
  { value: '#8B5CF6', name: 'Purple', device_color: 'purple' },
  { value: '#6366F1', name: 'Indigo' },
  { value: '#3B82F6', name: 'Blue', device_color: 'blue' },
  { value: '#06B6D4', name: 'Cyan', device_color: 'cyan' },
  { value: '#14B8A6', name: 'Teal' },
  { value: '#10B981', name: 'Green', device_color: 'green' },
  { value: '#84CC16', name: 'Olive', device_color: 'olive' },
  { value: '#059669', name: 'Emerald' },
  { value: DEFAULT_LABEL_COLOR, name: 'Gray', device_color: 'gray' },
  { value: '#475569', name: 'Slate' },
];

/** The names KOReader stores for the nine colours it offers. */
export const DEVICE_COLORS: readonly string[] = LABEL_COLORS.flatMap(
  (option) => option.device_color ?? []
);
