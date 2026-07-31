import { setupWorker } from 'msw/browser';
import { authHandlers } from './auth';

export const worker = setupWorker(...authHandlers);
