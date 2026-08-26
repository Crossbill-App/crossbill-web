import { CloseIcon } from '@/theme/Icons.tsx';
import { Box, Drawer, IconButton, Tab, Tabs } from '@mui/material';
import { type ReactNode, useState } from 'react';

export interface FilterTab {
  label: string;
  content: ReactNode;
}

interface FilterDrawerProps {
  open: boolean;
  onClose: () => void;
  tabs: FilterTab[];
  header?: ReactNode;
}

export const FilterDrawer = ({ open, onClose, tabs, header }: FilterDrawerProps) => {
  const [activeTab, setActiveTab] = useState(0);

  const handleClose = () => {
    onClose();
    setActiveTab(0);
  };

  return (
    <Drawer anchor="bottom" open={open} onClose={handleClose}>
      <Box sx={{ p: 2, pb: 6, maxHeight: '80vh', overflow: 'auto' }}>
        {/* Drag handle */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
          <Box
            sx={{
              width: 40,
              height: 4,
              borderRadius: 2,
              bgcolor: 'grey.300',
            }}
          />
        </Box>

        {/* Close button */}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
          <IconButton edge="end" onClick={handleClose} aria-label="close" size="small">
            <CloseIcon />
          </IconButton>
        </Box>

        {header && <Box sx={{ mb: 2 }}>{header}</Box>}

        {/* Tabs */}
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
          variant="fullWidth"
          sx={{ mb: 2 }}
        >
          {tabs.map((tab, i) => (
            <Tab key={i} label={tab.label} />
          ))}
        </Tabs>

        {/* Tab content */}
        {tabs[activeTab]?.content}
      </Box>
    </Drawer>
  );
};
