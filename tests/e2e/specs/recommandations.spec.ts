import { expect, test, type Page } from '@playwright/test';

import { comptes } from '../support/comptes';
import { fermerSession, ouvrirSession } from '../support/session';

test.describe.configure({ mode: 'serial' });
let page: Page;

test.beforeAll(async ({ browser }) => {
  page = await ouvrirSession(browser, comptes.admin);
});
test.afterAll(async () => fermerSession(page));

test('génère les recommandations à partir des alertes', async () => {
  await page.goto('/recommendations');
  await page.getByTestId('generate').click();

  await expect(page.getByRole('alert').filter({ hasText: /alertes? examinées?/ })).toBeVisible();
  await expect(page.locator('[id^="alerte-"]').first()).toBeVisible();
  await expect(page.locator('.reco__action').first()).not.toBeEmpty();
});

test("isole les recommandations d'une alerte", async () => {
  const carte = page.locator('[id^="alerte-"]').first();
  const identifiant = (await carte.getAttribute('id'))?.replace('alerte-', '');
  expect(identifiant).toBeTruthy();

  await page.goto(`/recommendations?alert=${identifiant}`);

  await expect(page.getByText(`Alerte n° ${identifiant}`)).toBeVisible();
  await expect(page.locator(`#alerte-${identifiant}`)).toBeVisible();
});
