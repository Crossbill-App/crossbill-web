import { createTheme, type CSSProperties, type Theme } from '@mui/material/styles';

const colors = {
  amber: {
    600: '#685A4B',
    700: '#43311E',
    800: '#2E2215',
  },
  stone: {
    50: '#fafaf9',
    100: '#f5f5f4',
    400: '#a8a29e',
    600: '#78716c',
    700: '#57534e',
    900: '#1c1917',
  },
};

/**
 * Custom colors used throughout the application.
 * These are consolidated from various rgba() calls in components.
 */
const customColors = {
  // Highlight colors for scroll-to-highlight effects
  highlightBlue: {
    light: 'rgba(25, 118, 210, 0.08)', // Light blue for highlight effect (BookPage)
  },

  // Translucent whites, for the one place they belong: over the amber app bar,
  // where what sits behind them is known and fixed.
  whiteOverlay: {
    light: 'rgba(255, 255, 255, 0.1)', // White overlay for hover effects (AppBar)
    hover: 'rgba(255, 255, 255, 0.18)', // Search field surface on hover (AppBar)
  },

  // Opaque panel fills. A white veil reads only against a darker page — these
  // are the same on the stone page background and on a paper-white drawer.
  surfaces: {
    tagGroup: colors.stone[100], // Tag group panel (TagsList)
    tagUngrouped: colors.stone[50], // Ungrouped tag bucket, with its dashed border
  },

  // Shadow colors
  shadows: {
    light: 'rgba(0, 0, 0, 0.04)', // Very light shadow (HighlightCard)
    medium: 'rgba(0, 0, 0, 0.15)', // Medium shadow (BookCard)
  },

  // Drag and drop colors (using amber[600] as base: #685A4B)
  dragDrop: {
    hoverBg: 'rgba(104, 90, 75, 0.08)', // Light amber for hover background
    hoverBorder: 'rgba(104, 90, 75, 0.4)', // Medium amber for border when dragging over
    transparent: 'rgba(104, 90, 75, 0)', // Transparent amber for transitions
  },

  // Border colors
  borders: {
    light: 'rgba(0, 0, 0, 0.12)', // Light border for empty states
    transparent: 'rgba(0, 0, 0, 0)', // Transparent border
  },

  // Background colors
  backgrounds: {
    subtle: 'rgba(0, 0, 0, 0.05)', // Very subtle background (dialog ProgressBar track, markdown code blocks, chat bubbles)
  },
};

/** Devices pointed at with a finger or a stylus, rather than a mouse. */
const COARSE_POINTER_QUERY = '@media (pointer: coarse)';

/** Material Design's minimum touch target, in px. */
const TOUCH_TARGET_MIN = 48;

/**
 * Shared markdown styles for consistent rendering across the application.
 * Used in components that render markdown content (e.g., AI summaries).
 */
export const markdownStyles = (theme: Theme) => ({
  ...theme.typography.body1,
  color: theme.palette.text.primary,

  '& p': {
    margin: 0,
    marginBottom: '0.5em',
    '&:last-child': {
      marginBottom: 0,
    },
  },
  '& ul, & ol': {
    marginTop: '0.5em',
    marginBottom: '0.5em',
    paddingLeft: '1.5em',
  },
  '& li': {
    marginBottom: '0.25em',
  },
  // Headings in user markdown are content sub-structure — keep them below
  // the app's own heading scale so they never compete with page titles.
  '& h1, & h2, & h3, & h4': {
    fontSize: '1.05rem',
    fontWeight: 600,
    margin: '0.75em 0 0.25em',
    '&:first-of-type': { marginTop: 0 },
  },
  '& strong': {
    fontWeight: 600,
  },
  '& em': {
    fontStyle: 'italic',
  },
  '& code': {
    fontFamily: 'monospace',
    backgroundColor: customColors.backgrounds.subtle,
    padding: '0.125em 0.25em',
    borderRadius: '0.25em',
    fontSize: '0.9em',
  },
  '& pre': {
    backgroundColor: customColors.backgrounds.subtle,
    padding: '0.75em',
    borderRadius: '0.5em',
    overflow: 'auto',
    marginTop: '0.5em',
    marginBottom: '0.5em',
  },
  '& pre code': {
    backgroundColor: 'transparent',
    padding: 0,
  },
});

// Extend the MUI Theme interface to include custom colors
declare module '@mui/material/styles' {
  interface Theme {
    customColors: typeof customColors;
  }
  interface ThemeOptions {
    customColors?: typeof customColors;
  }
  interface TypographyVariants {
    pageTitle: CSSProperties;
    sectionTitle: CSSProperties;
  }
  interface TypographyVariantsOptions {
    pageTitle?: CSSProperties;
    sectionTitle?: CSSProperties;
  }
}

declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    pageTitle: true;
    sectionTitle: true;
  }
}

export const theme = createTheme({
  customColors,
  palette: {
    mode: 'light',
    primary: {
      main: colors.amber[700],
      light: colors.amber[600],
      dark: colors.amber[800],
      contrastText: '#ffffff',
    },
    secondary: {
      main: colors.stone[600],
      light: colors.stone[400],
      dark: colors.stone[700],
      contrastText: '#ffffff',
    },
    background: {
      default: colors.stone[50],
      paper: '#ffffff',
    },
    text: {
      primary: colors.stone[900],
      secondary: colors.stone[600],
    },
  },
  typography: {
    fontFamily: ['"Lora"', 'Georgia', 'serif'].join(','),
    h1: {
      fontSize: '2rem',
      fontWeight: 900,
      letterSpacing: '-0.02em',
      lineHeight: 1.2,
    },
    h2: {
      fontSize: '1.4rem',
      fontWeight: 200,
      lineHeight: 1.3,
    },
    h3: {
      fontSize: '1.1rem',
      fontWeight: 800,
      letterSpacing: '0.01em',
    },
    h4: {
      fontSize: '1.0rem',
      fontWeight: 700,
    },
    h5: {
      fontSize: '1.0rem',
      fontWeight: 700,
    },
    h6: {
      fontSize: '1.0rem',
      fontWeight: 600,
    },
    body1: {
      fontSize: '1.0rem',
      fontWeight: 400, // Light for readability
      lineHeight: 1.75,
      letterSpacing: '0.01em',
    },
    body2: {
      fontWeight: 200, // Very light
      lineHeight: 1.6,
    },
    /**
     * The heading a page leads with. Its own variant rather than `h2` with
     * three corrections at the call site, which is how the weight drifted:
     * `h2` is the light subtitle weight a book's author line uses, and a page
     * title is the heavy one.
     */
    pageTitle: {
      fontSize: '1.4rem',
      fontWeight: 900,
      lineHeight: 1.3,
      color: colors.amber[700],
    },
    /** The heading of every section sitting under a page title. */
    sectionTitle: {
      fontSize: '1.1rem',
      fontWeight: 800,
      letterSpacing: '0.01em',
      color: colors.amber[700],
    },
  },
  shape: {
    borderRadius: 12,
  },
  shadows: [
    'none',
    '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)', // shadow-sm
    '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)', // shadow-md
    '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)', // shadow-lg
    '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)', // shadow-xl
    '0 25px 50px -12px rgb(0 0 0 / 0.25)', // shadow-2xl
    '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
    '0 25px 50px -12px rgb(0 0 0 / 0.25)',
    '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
    '0 25px 50px -12px rgb(0 0 0 / 0.25)',
    '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
    '0 25px 50px -12px rgb(0 0 0 / 0.25)',
    '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        // Kills the iOS rubber-band bounce, so a downward drag at the top of
        // the page belongs to the pull-to-refresh gesture alone.
        'html, body': {
          overscrollBehaviorY: 'contain',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 24,
          fontWeight: 500,
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        // A fingertip has no pixel precision, so every icon button clears the
        // 48dp touch target wherever the pointer is coarse, whatever `size`
        // its call site asked for. A mouse keeps the compact button.
        root: {
          [COARSE_POINTER_QUERY]: {
            minWidth: TOUCH_TARGET_MIN,
            minHeight: TOUCH_TARGET_MIN,
            // Except inside a text field: an Autocomplete's clear and dropdown
            // marks, or a date picker's calendar, would stretch the field.
            '.MuiInputBase-root &': {
              minWidth: 'unset',
              minHeight: 'unset',
            },
          },
        },
      },
    },
    MuiTypography: {
      defaultProps: {
        // Custom variants have no element of their own without this, so a page
        // title written as `<Typography variant="pageTitle">` would render a
        // paragraph.
        variantMapping: {
          pageTitle: 'h2',
          sectionTitle: 'h2',
        },
      },
    },
    MuiChip: {
      // Every chip in the app is a small one, from a tag to a filter to the
      // "not on device" marker.
      defaultProps: { size: 'small' },
      styleOverrides: {
        root: ({ theme: t }) => ({
          variants: [
            {
              // A chip you can click selects something — a tag, a label, a
              // note type, a reading stage. One geometry and one motion for
              // all of them, so chips sitting in the same drawer cannot
              // behave differently.
              props: ({ ownerState }) => Boolean(ownerState.clickable),
              style: {
                padding: '2px 4px',
                transition: 'all 0.2s ease',
              },
            },
            {
              props: ({ ownerState }) =>
                Boolean(ownerState.clickable) && ownerState.variant === 'outlined',
              style: {
                borderColor: t.palette.divider,
                '&:hover': {
                  backgroundColor: t.palette.action.hover,
                  borderColor: t.palette.secondary.light,
                  transform: 'translateY(-1px)',
                },
              },
            },
            {
              props: ({ ownerState }) =>
                Boolean(ownerState.clickable) && ownerState.variant === 'filled',
              style: {
                '&:hover': {
                  backgroundColor: t.palette.primary.dark,
                  transform: 'translateY(-1px)',
                },
              },
            },
          ],
        }),
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          border: `1px solid ${colors.stone[400]}`,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        rounded: {
          borderRadius: 16,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: colors.stone[50], // Same as body background
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 12,
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: colors.amber[700],
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: colors.amber[700],
              borderWidth: 2,
            },
          },
          '& .MuiInputBase-input': {
            fontSize: '1rem',
            fontWeight: 400,
            letterSpacing: '0.01em',
          },
        },
      },
    },
  },
});
