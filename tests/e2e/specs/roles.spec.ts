import { expect, test, type Page } from '@playwright/test';

import { comptes } from '../support/comptes';
import { fermerSession, ouvrirSession } from '../support/session';

test.describe('lecteur', () => {
  test.describe.configure({ mode: 'serial' });
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    page = await ouvrirSession(browser, comptes.lecteur);
  });
  test.afterAll(async () => fermerSession(page));

  test('ne voit ni la supervision des capteurs ni la génération', async () => {
    await expect(page.getByRole('link', { name: 'Voir les sites' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Supervision des capteurs' })).toHaveCount(0);

    await page.getByRole('link', { name: 'Recommandations', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Recommandations' })).toBeVisible();
    await expect(page.getByTestId('generate')).toHaveCount(0);
  });

  test('est renvoyé vers la connexion sur la page réservée aux administrateurs', async () => {
    await page.goto('/monitoring/sensors');

    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe('opérateur', () => {
  test('voit le tableau de bord sans la supervision des capteurs', async ({ browser }) => {
    const page = await ouvrirSession(browser, comptes.operateur);

    await expect(page.getByRole('heading', { name: "Vue d'ensemble" })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Supervision des capteurs' })).toHaveCount(0);

    await fermerSession(page);
  });
});

test.describe('administrateur', () => {
  test('suit la santé des capteurs de chaque site', async ({ browser }) => {
    const page = await ouvrirSession(browser, comptes.admin);

    await page.getByRole('link', { name: 'Supervision des capteurs' }).click();
    await expect(page.getByRole('heading', { name: 'Supervision des capteurs' })).toBeVisible();

    const cartes = page.getByTestId('site-card');
    await expect(cartes.filter({ hasText: 'Siège Part-Dieu' })).toContainText('ok');
    await expect(cartes.filter({ hasText: 'Groupe scolaire Gratte-Ciel' })).toContainText(
      'degraded',
    );

    await fermerSession(page);
  });
});
