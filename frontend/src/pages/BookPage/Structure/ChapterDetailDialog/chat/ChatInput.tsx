import { SendIcon } from '@/theme/Icons.tsx';
import { Box, IconButton, InputAdornment, TextField } from '@mui/material';
import { useCallback } from 'react';

interface ChatInputProps {
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled: boolean;
  sendDisabled: boolean;
}

export const ChatInput = ({
  value,
  placeholder,
  onChange,
  onSend,
  disabled,
  sendDisabled,
}: ChatInputProps) => {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    },
    [onSend]
  );

  return (
    <Box sx={{ position: 'sticky', bottom: 0, pt: 1 }}>
      <TextField
        fullWidth
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        multiline
        maxRows={3}
        sx={{ '& .MuiOutlinedInput-root': { bgcolor: 'background.default' } }}
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={onSend} disabled={sendDisabled} color="primary">
                  <SendIcon />
                </IconButton>
              </InputAdornment>
            ),
          },
        }}
      />
    </Box>
  );
};
