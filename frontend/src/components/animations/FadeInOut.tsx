import { motion } from 'motion/react';
import { useState } from 'react';

const ENTER = { opacity: 0, y: 20 };

interface FadeInOutProps {
  children: React.ReactNode;
  ekey: React.Key;
  /**
   * Set to false when an ancestor already fades this content in on first
   * paint. The wrapper then only animates once `ekey` changes, so the two
   * fades do not stack into a double opacity ramp and a doubled y offset.
   */
  animateOnMount?: boolean;
}

export const FadeInOut = ({ children, ekey, animateOnMount = true }: FadeInOutProps) => {
  // `ekey` keys the inner motion.div, not this component, so this component
  // survives key changes and can tell the first paint from a later swap.
  const [renderedKey, setRenderedKey] = useState(ekey);
  const [shouldAnimate, setShouldAnimate] = useState(animateOnMount);
  if (renderedKey !== ekey) {
    setRenderedKey(ekey);
    setShouldAnimate(true);
  }

  return (
    <motion.div
      key={ekey}
      initial={shouldAnimate ? ENTER : false}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
};
