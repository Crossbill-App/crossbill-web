import type { HighlightLabelInBook } from '@/api/generated/model';
import { hexTint, LABEL_COLORS } from '@/utils/colorUtils.ts';

/** One colour a highlight can be made in, as the popover offers it. */
export interface HighlightColor {
  /** The name KOReader stores, which is what the server files the highlight by. */
  device_color: string;
  name: string;
  tint: string;
}

// Only the colour's own drawer counts: a `yellow`/`underscore` style names
// something the reader draws differently, so its name is not yellow's.
const LIGHTEN = 'lighten';

/** The nine KOReader colours, each wearing the book's own label for it where the book has one. */
export const paletteFor = (labels: HighlightLabelInBook[]): HighlightColor[] =>
  LABEL_COLORS.flatMap((option) => {
    const device_color = option.device_color;
    if (!device_color) return [];
    const label = labels.find(
      (candidate) => candidate.device_color === device_color && candidate.device_style === LIGHTEN
    );
    return [
      {
        device_color,
        name: label?.label || option.name,
        tint: hexTint(label?.ui_color, option.value),
      },
    ];
  });
