import type { ChapterDigestResponse } from '@/api/generated/model';
import { markdownStyles } from '@/theme/theme';
import { Box, CircularProgress, Typography, styled } from '@mui/material';
import ReactMarkdown from 'react-markdown';

interface DigestContentProps {
  content?: ChapterDigestResponse | null;
  isGenerating?: boolean;
}

const MarkdownList = styled('ul')(({ theme }) => ({
  ...markdownStyles(theme),
  margin: 0,
  paddingLeft: theme.spacing(3),
  '& li': {
    marginBottom: theme.spacing(1),
  },
}));

export const DigestContent = ({ content, isGenerating }: DigestContentProps) => {
  if (isGenerating) {
    return (
      <Box sx={(theme) => ({ p: theme.spacing(2), textAlign: 'center' })}>
        <CircularProgress size={24} />
        <Typography
          variant="body2"
          sx={[
            {
              color: 'text.secondary',
            },
            (theme) => ({ mt: theme.spacing(1) }),
          ]}
        >
          Generating summary...
        </Typography>
      </Box>
    );
  }

  if (!content) {
    return null;
  }

  return (
    <Box sx={(theme) => ({ mb: theme.spacing(2) })}>
      <Typography variant="body1" sx={(theme) => ({ mb: theme.spacing(2.5) })}>
        {content.summary}
      </Typography>

      <Typography variant="body1" sx={(theme) => ({ mb: theme.spacing(1.5), fontWeight: 600 })}>
        Key Points:
      </Typography>
      <MarkdownList>
        {content.keypoints.map((point, idx) => (
          <li key={idx}>
            <ReactMarkdown>{point}</ReactMarkdown>
          </li>
        ))}
      </MarkdownList>

      <Typography
        variant="caption"
        sx={[
          {
            color: 'text.secondary',
          },
          (theme) => ({ display: 'block', mt: theme.spacing(3) }),
        ]}
      >
        Generated on {new Date(content.generated_at).toLocaleDateString()}
      </Typography>
    </Box>
  );
};
