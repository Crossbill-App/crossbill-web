import { i18n } from '@/i18n';
import type { en } from '@/i18n/locales/en';

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

type ColorName = keyof typeof en.components.colors;

// `name` is a getter, so each read resolves the copy in the current language
// rather than freezing whatever it was when this module loaded.
const colorOption = (value: string, nameKey: ColorName, device_color?: string): ColorOption => ({
  value,
  get name() {
    return i18n.t(`components.colors.${nameKey}`);
  },
  ...(device_color && { device_color }),
});

export const LABEL_COLORS: readonly ColorOption[] = [
  colorOption('#F59E0B', 'yellow', 'yellow'),
  colorOption('#F97316', 'orange', 'orange'),
  colorOption('#EF4444', 'red', 'red'),
  colorOption('#EC4899', 'pink'),
  colorOption('#8B5CF6', 'purple', 'purple'),
  colorOption('#6366F1', 'indigo'),
  colorOption('#3B82F6', 'blue', 'blue'),
  colorOption('#06B6D4', 'cyan', 'cyan'),
  colorOption('#14B8A6', 'teal'),
  colorOption('#10B981', 'green', 'green'),
  colorOption('#84CC16', 'olive', 'olive'),
  colorOption('#059669', 'emerald'),
  colorOption(DEFAULT_LABEL_COLOR, 'gray', 'gray'),
  colorOption('#475569', 'slate'),
];

/** The names KOReader stores for the nine colours it offers. */
export const DEVICE_COLORS: readonly string[] = LABEL_COLORS.flatMap(
  (option) => option.device_color ?? []
);
