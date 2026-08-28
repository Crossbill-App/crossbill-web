import { markdownStyles } from '@/theme/theme';
import { Box, Button, useTheme } from '@mui/material';
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';

interface BookBlurbProps {
  description: string | null;
}

const COLLAPSED_LINES = 3;

/**
 * The book's blurb, collapsed to a few lines under the header stats.
 *
 * Publisher metadata arrives as HTML far more often than as Markdown, so
 * `rehypeRaw` renders the tags rather than showing them as text. That makes
 * `rehypeSanitize` mandatory rather than optional: the same field is editable
 * by the reader, so unsanitised raw HTML here would be stored XSS.
 */
export const BookBlurb = ({ description }: BookBlurbProps) => {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(false);
  const clamped = useRef<HTMLDivElement>(null);
  const overflows = useOverflows(clamped, description, expanded);

  if (!description?.trim()) return null;

  return (
    <Box sx={{ width: '100%', mb: 2 }}>
      <Box
        ref={clamped}
        sx={{
          ...markdownStyles(theme),
          color: 'text.secondary',
          ...(expanded
            ? {}
            : {
                display: '-webkit-box',
                WebkitLineClamp: COLLAPSED_LINES,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }),
        }}
      >
        <ReactMarkdown rehypePlugins={[rehypeRaw, rehypeSanitize]}>{description}</ReactMarkdown>
      </Box>
      {(overflows || expanded) && (
        <Button
          variant="text"
          size="small"
          sx={{ px: 0 }}
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
        >
          {expanded ? 'Show less' : 'Show more'}
        </Button>
      )}
    </Box>
  );
};

const useOverflows = (
  ref: React.RefObject<HTMLElement | null>,
  description: string | null,
  expanded: boolean
) => {
  const [overflows, setOverflows] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element || expanded) return;

    const measure = () => setOverflows(element.scrollHeight > element.clientHeight);
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, description, expanded]);

  return overflows;
};
