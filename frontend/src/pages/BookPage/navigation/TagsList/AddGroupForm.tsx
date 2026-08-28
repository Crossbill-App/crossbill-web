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
            {/* The dialog footer convention: a right-aligned text Cancel
                beside a contained primary. */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
              <Button size="small" onClick={onCancel}>
                Cancel
              </Button>
              <Button
                size="small"
                variant="contained"
                onClick={handleSubmit}
                disabled={isProcessing}
              >
                Add group
              </Button>
            </Box>
          </Box>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
