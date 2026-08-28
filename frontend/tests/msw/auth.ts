import { http, HttpResponse } from 'msw';
import { appSettings, aTokenResponse, aUser } from '../fixtures/auth';

export const authHandlers = [
  http.post('/api/v1/auth/refresh', () => HttpResponse.json(aTokenResponse())),
  http.post('/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/v1/users/me', () => HttpResponse.json(aUser())),
  http.get('/api/v1/settings', () => HttpResponse.json(appSettings())),
];

/** Settings with the embeddings feature flag forced on or off. */
export const settingsWithEmbeddings = (enabled: boolean) =>
  http.get('/api/v1/settings', () =>
    HttpResponse.json(
      appSettings({ feature_flags: { ai: false, embeddings: enabled, user_registrations: false } })
    )
  );

/** Settings with the AI feature flag forced on or off. */
export const settingsWithAi = (enabled: boolean) =>
  http.get('/api/v1/settings', () =>
    HttpResponse.json(
      appSettings({ feature_flags: { ai: enabled, embeddings: false, user_registrations: false } })
    )
  );
