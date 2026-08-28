import { Box, Button, ClickAwayListener, TextField } from '@mui/material';
import { AnimatePresence, motion } from 'motion/react';
import { KeyboardEvent, useState } from 'react';

interface AddGroupFormProps {
  isVisible: boolean;
  isProcessing: boolean;
  onSubmit: (newGroupName: string) => void;
  onCancel: () => void;
}

export const AddGroupForm = ({
  isVisible,
  isProcessing,
  onSubmit,
  onCancel,
}: AddGroupFormProps) => {
  const [groupName, setGroupName] = useState('');

  const handleSubmit = () => {
    onSubmit(groupName);
    setGroupName('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'Escape') {
      onCancel();
    }
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.15 }}
          style={{ overflow: 'hidden' }}
        >
          <Box
            sx={{
              mb: 2,
              p: 1.5,
              bgcolor: 'action.hover',
              borderRadius: 1,
              border: '1px dashed',
              borderColor: 'divider',
            }}
          >
            <ClickAwayListener onClickAway={handleSubmit}>
              <TextField
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Group name..."
                size="small"
                autoFocus
                disabled={isProcessing}
                fullWidth
                sx={{ mb: 1 }}
              />
            </ClickAwayListener>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={isProcessing}
                sx={{
                  flex: 1,
                  fontSize: '0.75rem',
                }}
              >
                Add group
              </Button>
              <Button
                variant="outlined"
                onClick={onCancel}
                sx={{
                  flex: 1,
                  fontSize: '0.75rem',
                }}
              >
                Cancel
              </Button>
            </Box>
          </Box>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
