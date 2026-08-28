import { ScrollToTopIcon } from '@/theme/Icons.tsx';
import { Fab, Zoom } from '@mui/material';
import { useEffect, useState } from 'react';

interface ScrollToTopButtonProps {
  /**
   * The scroll threshold in pixels after which the button appears.
   * @default 300
   */
  scrollThreshold?: number;
  /**
   * The scroll behavior when clicking the button.
   * @default 'smooth'
   */
  scrollBehavior?: ScrollBehavior;
}

export const ScrollToTopButton = ({
  scrollThreshold = 300,
  scrollBehavior = 'smooth',
}: ScrollToTopButtonProps) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      const scrolled = window.scrollY > scrollThreshold;
      setIsVisible(scrolled);
    };

    window.addEventListener('scroll', handleScroll);
    handleScroll();

    // Cleanup
    return () => window.removeEventListener('scroll', handleScroll);
  }, [scrollThreshold]);

  const handleClick = () => {
    window.scrollTo({
      top: 0,
      behavior: scrollBehavior,
    });
  };

  return (
    <Zoom in={isVisible} mountOnEnter unmountOnExit>
      {/* Deliberately neutral: in this stack amber means "something is
          filtered", and scrolling to the top is not a state. */}
      <Fab size="small" aria-label="Scroll to top" onClick={handleClick}>
        <ScrollToTopIcon />
      </Fab>
    </Zoom>
  );
};
