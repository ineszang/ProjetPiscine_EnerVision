import { expect, test, type Page } from '@playwright/test';

import { comptes } from '../support/comptes';
import { fermerSession, ouvrirSession } from '../support/session';

test.describe.configure({ mode: 'serial' });
let page: Page;

const fil = () => page.getByRole('complementary', { name: 'Alertes actives' });
const alertes = () => fil().locator('li.alert-feed__item');

test.beforeAll(async ({ browser }) => {
  page = await ouvrirSession(browser, comptes.lecteur);
});
test.afterAll(async () => fermerSession(page));

test('affiche dix alertes, puis les suivantes à la demande', async () => {
  await expect(alertes()).toHaveCount(10);
  const plus = fil().getByTestId('show-more');
  await expect(plus).toBeVisible();

  await plus.click();

  await expect.poll(async () => alertes().count()).toBeGreaterThan(10);
});

test('filtre par sévérité', async () => {
  await fil().getByTestId('severity-filter').selectOption('critical');

  await expect(alertes().first()).toBeVisible();
  const severites = await alertes().evaluateAll((items) =>
    items.map((item) => item.className.includes('alert-feed__item--critical')),
  );
  expect(severites.every(Boolean)).toBe(true);
});

test('annonce un fil vide quand aucun critère ne correspond', async () => {
  await fil().getByTestId('site-filter').selectOption('demo-ecole');

  await expect(fil().getByText('Aucune alerte pour ces critères.')).toBeVisible();
  await expect(alertes()).toHaveCount(0);
});
