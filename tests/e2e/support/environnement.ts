export const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:4200';
export const API_URL = new URL('/api/v1/', BASE_URL).toString();
export const MAILPIT_URL = process.env.E2E_MAILPIT_URL ?? 'http://localhost:8025';
