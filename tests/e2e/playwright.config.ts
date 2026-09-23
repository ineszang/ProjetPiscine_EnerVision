import { defineConfig, devices } from '@playwright/test';

import { BASE_URL } from './support/environnement';

const enCi = Boolean(process.env.CI);

// Piège : un seul worker. La zone `auth` de nginx admet 30 connexions par minute, et deux
// fichiers en parallèle dépasseraient sa rafale de 20 dès le démarrage de la suite.
export default defineConfig({
  testDir: './specs',
  fullyParallel: false,
  workers: 1,
  forbidOnly: enCi,
  retries: enCi ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: enCi
    ? [['list'], ['github'], ['html', { open: 'never' }]]
    : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    ignoreHTTPSErrors: true,
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
