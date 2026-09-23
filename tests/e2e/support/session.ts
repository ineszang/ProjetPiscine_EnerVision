import { expect, type Browser, type Page } from '@playwright/test';

import type { Compte } from './comptes';
import { BASE_URL } from './environnement';

export async function seConnecter(page: Page, compte: Compte): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(compte.email);
  await page.getByLabel('Mot de passe').fill(compte.password);
  await page.getByRole('button', { name: 'Se connecter' }).click();
}

// Pourquoi : une session par fichier, pas par test. Rejouer un même cookie de refresh dans deux
// contextes révoque toute sa famille (ADR 0002), d'où ni `storageState` partagé ni reconnexions.
export async function ouvrirSession(browser: Browser, compte: Compte): Promise<Page> {
  const contexte = await browser.newContext({
    baseURL: BASE_URL,
    ignoreHTTPSErrors: true,
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
  });
  const page = await contexte.newPage();
  await seConnecter(page, compte);
  await expect(page).toHaveURL(/\/dashboard$/);
  return page;
}

export async function fermerSession(page: Page): Promise<void> {
  await page.context().close();
}
