import { expect, test } from '@playwright/test';

import { comptes } from '../support/comptes';
import { seConnecter } from '../support/session';

test('renvoie vers la connexion sans session', async ({ page }) => {
  await page.goto('/dashboard');

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Connexion' })).toBeVisible();
});

test('refuse des identifiants incorrects', async ({ page }) => {
  await seConnecter(page, { email: comptes.lecteur.email, password: 'Mauvais-mot-de-passe-1!' });

  await expect(page.getByRole('alert')).toContainText('Email ou mot de passe incorrect.');
  await expect(page).toHaveURL(/\/login$/);
});

test('ouvre le tableau de bord, garde la session au rechargement puis la ferme', async ({
  page,
}) => {
  await seConnecter(page, comptes.lecteur);

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: "Vue d'ensemble" })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Indicateurs du parc' })).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Alertes actives' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('heading', { name: "Vue d'ensemble" })).toBeVisible();

  await page.getByRole('button', { name: 'Déconnexion' }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login$/);
});
