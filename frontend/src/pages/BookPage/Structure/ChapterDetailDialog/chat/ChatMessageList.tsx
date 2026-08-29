import { Box, CircularProgress, Typography, useTheme } from '@mui/material';
import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';

import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { NoteAddIcon } from '@/theme/Icons.tsx';
import { markdownStyles } from '@/theme/theme';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatMessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  onSaveNote?: (content: string) => void;
}

export const ChatMessageList = ({
  messages,
  isLoading,
  error,
  onSaveNote,
}: ChatMessageListProps) => {
  const theme = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, error]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        mt: 2,
        mb: 2,
      }}
    >
      {messages.map((msg, i) => (
        <Box
          key={i}
          sx={{
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '80%',
            p: 1.5,
            borderRadius: 2,
            bgcolor: msg.role === 'user' ? 'primary.main' : theme.customColors.backgrounds.subtle,
            color: msg.role === 'user' ? 'primary.contrastText' : 'text.primary',
          }}
        >
          {msg.role === 'assistant' ? (
            <>
              <Box sx={markdownStyles(theme)}>
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </Box>
              {onSaveNote && (
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
                  <IconButtonWithTooltip
                    label="Save as note"
                    onClick={() => onSaveNote(msg.content)}
                    icon={<NoteAddIcon fontSize="small" />}
                  />
                </Box>
              )}
            </>
          ) : (
            <Typography variant="body1">{msg.content}</Typography>
          )}
        </Box>
      ))}

      {isLoading && (
        <Box sx={{ alignSelf: 'flex-start' }}>
          <CircularProgress size={24} />
        </Box>
      )}

      <div ref={messagesEndRef} />
    </Box>
  );
};
