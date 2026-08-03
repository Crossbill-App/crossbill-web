import type { AppSettingsResponse, FeatureFlags } from '@/api/generated/model';
import { getAppSettings } from '@/api/generated/settings/settings';
import { createContext, ReactNode, useContext, useEffect, useState } from 'react';

interface SettingsContextType {
  settings: AppSettingsResponse | null;
  featureFlags: FeatureFlags | undefined;
  isLoading: boolean;
}

const SettingsContext = createContext<SettingsContextType | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettingsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch settings on mount
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const settingsData = await getAppSettings();
        setSettings(settingsData);
      } catch (error) {
        console.error('Failed to fetch app settings:', error);
        // Set default settings on error
        setSettings({
          feature_flags: {
            ai: false,
            embeddings: false,
            user_registrations: false,
          },
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchSettings();
  }, []);

  return (
    <SettingsContext.Provider
      value={{
        settings,
        featureFlags: settings?.feature_flags,
        isLoading,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}
