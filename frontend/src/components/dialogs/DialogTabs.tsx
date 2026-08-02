import { Box, Tab, Tabs } from '@mui/material';
import { type ReactNode, useId, useState } from 'react';
import type { SwipeableHandlers } from 'react-swipeable';

export interface DialogTabItem {
  key: string;
  label: string;
  /** Shown as "Label (n)" when > 0; omit for count-less tabs. */
  count?: number;
  content: ReactNode;
}

interface DialogTabsProps {
  tabs: DialogTabItem[];
  /** Spread on the tab panel so swipes there can drive modal navigation. */
  panelSwipeHandlers?: SwipeableHandlers;
  /**
   * Controlled mode: lift the tab state to the caller when it must survive
   * remounts (e.g. content wrapped in a keyed `FadeInOut`).
   */
  activeTab?: number;
  onTabChange?: (index: number) => void;
}

const formatTabLabel = (label: string, count?: number) =>
  count !== undefined && count > 0 ? `${label} (${count})` : label;

/**
 * Shared tab strip + panel for the entity detail modals (highlight, note,
 * chapter). All tabs stay visible with an optional count suffix; only the
 * active tab's content is mounted, so sections can keep fetching lazily.
 * Touch events on the strip stop propagating so tab gestures don't trigger
 * the modals' horizontal swipe navigation.
 */
export const DialogTabs = ({
  tabs,
  panelSwipeHandlers,
  activeTab,
  onTabChange,
}: DialogTabsProps) => {
  const [internalTab, setInternalTab] = useState(0);
  const instanceId = useId();
  const currentTab = activeTab ?? internalTab;
  const setTab = onTabChange ?? setInternalTab;

  // Guard against the active index pointing past the available tabs.
  const safeActiveTab = Math.min(currentTab, tabs.length - 1);

  return (
    <Box>
      <Tabs
        value={safeActiveTab}
        onChange={(_, newValue: number) => setTab(newValue)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ borderBottom: 1, borderColor: 'divider' }}
        onTouchStart={(e) => e.stopPropagation()}
        onTouchMove={(e) => e.stopPropagation()}
        onTouchEnd={(e) => e.stopPropagation()}
        // Arrow keys belong to the tab strip while it holds focus; without this
        // the enclosing modal steals them to page to the previous/next entity.
        data-prevent-navigation="true"
      >
        {tabs.map((tab, index) => (
          <Tab
            key={tab.key}
            id={`${instanceId}-tab-${index}`}
            aria-controls={`${instanceId}-panel-${index}`}
            label={formatTabLabel(tab.label, tab.count)}
          />
        ))}
      </Tabs>
      <Box
        role="tabpanel"
        id={`${instanceId}-panel-${safeActiveTab}`}
        aria-labelledby={`${instanceId}-tab-${safeActiveTab}`}
        sx={{ pt: 2, pb: 2 }}
        {...panelSwipeHandlers}
      >
        {tabs[safeActiveTab]?.content}
      </Box>
    </Box>
  );
};
