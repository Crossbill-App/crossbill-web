import type { AppSettingsResponse, UserDetailsResponse } from '@/api/generated/model';

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export const aTokenResponse = (overrides: Partial<TokenResponse> = {}): TokenResponse => ({
  access_token: 'test-access-token',
  refresh_token: 'test-refresh-token',
  expires_in: 3600,
  ...overrides,
});

export const aUser = (overrides: Partial<UserDetailsResponse> = {}): UserDetailsResponse => ({
  id: 1,
  email: 'reader@example.com',
  ...overrides,
});

export const appSettings = (overrides: Partial<AppSettingsResponse> = {}): AppSettingsResponse => ({
  feature_flags: {
    ai: false,
    embeddings: false,
    user_registrations: false,
  },
  ...overrides,
});
