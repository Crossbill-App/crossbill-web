import { http, HttpResponse } from 'msw';
import { appSettings, aTokenResponse, aUser } from '../fixtures/auth';

export const authHandlers = [
  http.post('/api/v1/auth/refresh', () => HttpResponse.json(aTokenResponse())),
  http.post('/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/v1/users/me', () => HttpResponse.json(aUser())),
  http.get('/api/v1/settings', () => HttpResponse.json(appSettings())),
];
