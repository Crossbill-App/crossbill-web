import type { SxProps, Theme } from '@mui/material';

/** Matches touch devices: no hover, imprecise pointer. */
export const TOUCH_POINTER_QUERY = '@media (hover: none) and (pointer: coarse)';

/**
 * Configuration options for adaptive hover styles.
 */
export interface AdaptiveHoverOptions {
  /** Transition duration in seconds (default: 0.15) */
  transitionDuration?: number;
  /** Custom class name for the actions element (default: 'adaptive-actions') */
  actionsClassName?: string;
}

/**
 * Generates sx styles for adaptive hover actions.
 *
 * On touch devices (tablets, phones), actions are always visible for discoverability.
 * On desktop devices with precise pointers, actions are hidden until hover or keyboard focus.
 *
 * @param options Configuration options
 * @returns Object with `container` and `actions` sx props
 *
 * @example
 * ```tsx
 * const styles = createAdaptiveHoverStyles({ actionsClassName: 'my-actions' });
 * <Box sx={styles.container}>
 *   <Box className="my-actions" sx={styles.actions}>
 *     <IconButton>...</IconButton>
 *   </Box>
 * </Box>
 * ```
 */
export const createAdaptiveHoverStyles = (
  options: AdaptiveHoverOptions = {}
): {
  container: SxProps<Theme>;
  actions: SxProps<Theme>;
} => {
  const { transitionDuration = 0.15, actionsClassName = 'adaptive-actions' } = options;

  return {
    // Styles for the parent container
    container: {
      // On desktop with precise pointer: hide actions, reveal on hover/focus
      '@media (hover: hover) and (pointer: fine)': {
        [`&:hover .${actionsClassName}`]: {
          opacity: 1,
        },
        [`&:focus-within .${actionsClassName}`]: {
          opacity: 1,
        },
      },
    },
    // Styles for the actions container
    actions: {
      display: 'flex',
      alignItems: 'center',
      transition: `opacity ${transitionDuration}s ease`,
      // Base state: visible on touch devices, hidden on desktop
      opacity: 1,
      '@media (hover: hover) and (pointer: fine)': {
        opacity: 0,
      },
    },
  };
};
