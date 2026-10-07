import type { IInjectablesConfig } from '@readium/navigator';
import libronBold from './fonts/libron/Libron-Bold.woff2?url';
import libronBoldItalic from './fonts/libron/Libron-BoldItalic.woff2?url';
import libronItalic from './fonts/libron/Libron-Italic.woff2?url';
import libronRegular from './fonts/libron/Libron-Regular.woff2?url';
import openDyslexicBold from './fonts/opendyslexic/OpenDyslexic-Bold.woff2?url';
import openDyslexicBoldItalic from './fonts/opendyslexic/OpenDyslexic-BoldItalic.woff2?url';
import openDyslexicItalic from './fonts/opendyslexic/OpenDyslexic-Italic.woff2?url';
import openDyslexicRegular from './fonts/opendyslexic/OpenDyslexic-Regular.woff2?url';

interface BundledFontFace {
  family: string;
  url: string;
  weight: 400 | 700;
  style: 'normal' | 'italic';
}

const FONT_FACES: BundledFontFace[] = [
  { family: 'Libron', url: libronRegular, weight: 400, style: 'normal' },
  { family: 'Libron', url: libronItalic, weight: 400, style: 'italic' },
  { family: 'Libron', url: libronBold, weight: 700, style: 'normal' },
  { family: 'Libron', url: libronBoldItalic, weight: 700, style: 'italic' },
  { family: 'OpenDyslexic', url: openDyslexicRegular, weight: 400, style: 'normal' },
  { family: 'OpenDyslexic', url: openDyslexicItalic, weight: 400, style: 'italic' },
  { family: 'OpenDyslexic', url: openDyslexicBold, weight: 700, style: 'normal' },
  { family: 'OpenDyslexic', url: openDyslexicBoldItalic, weight: 700, style: 'italic' },
];

// Absolute, because the stylesheet is a blob and a blob URL is no base to
// resolve a relative one against.
const absolute = (url: string) => new URL(url, window.location.href).href;

const fontFaceRule = ({ family, url, weight, style }: BundledFontFace) =>
  `@font-face { font-family: "${family}"; src: url("${absolute(url)}") format("woff2"); font-weight: ${weight}; font-style: ${style}; }`;

// Readium writes its own policy into each frame, whose `font-src` admits only
// the book's own path. These are path-scoped sources, so the frame gains the
// font directories and not the rest of the origin, `/api/` included. Scripts and
// nested frames stay shut either way: `sanitizeResponse` adds a stricter policy.
const fontDirectories = () => [
  ...new Set(FONT_FACES.map(({ url }) => new URL('./', absolute(url)).href)),
];

/** The typefaces the app ships, declared in every chapter frame so a font family preference can name them. */
export const bundledFontInjectables = (): IInjectablesConfig => ({
  allowedDomains: fontDirectories(),
  rules: [
    {
      resources: [/.*/],
      append: [
        {
          id: 'crossbill-bundled-fonts',
          as: 'link',
          rel: 'stylesheet',
          blob: new Blob([FONT_FACES.map(fontFaceRule).join('\n')], { type: 'text/css' }),
        },
      ],
    },
  ],
});
