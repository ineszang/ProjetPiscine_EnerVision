import { expect, test, type Page } from '@playwright/test';

import { comptes } from '../support/comptes';
import { fermerSession, ouvrirSession } from '../support/session';

test.describe.configure({ mode: 'serial' });
let page: Page;

test.beforeAll(async ({ browser }) => {
  page = await ouvrirSession(browser, comptes.lecteur);
});
test.afterAll(async () => fermerSession(page));

test('liste les sites du parc', async () => {
  await page.getByRole('link', { name: 'Voir les sites' }).click();

  await expect(page.getByRole('heading', { name: 'Sites' })).toBeVisible();
  await expect(page.getByRole('row', { name: /Siège Part-Dieu/ })).toBeVisible();
});

test('détaille un site : mesure instantanée et historique', async () => {
  await page
    .getByRole('row', { name: /Siège Part-Dieu/ })
    .getByRole('link', { name: 'Détail' })
    .click();

  await expect(page).toHaveURL(/\/sites\/demo-siege$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Siège Part-Dieu' })).toBeVisible();
  await expect(page.getByText('Mesure instantanée')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Historique de consommation' })).toBeVisible();
});

test('ouvre les recommandations filtrées sur ce site', async () => {
  await page.getByRole('link', { name: 'Voir dans la vue recommandations' }).click();

  await expect(page).toHaveURL(/\/recommendations\?site=demo-siege$/);
  await expect(page.getByTestId('site-filter')).toHaveValue('demo-siege');
});
