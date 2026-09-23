import { expect, test } from '@playwright/test';

import { creerCompteTemporaire, nouveauMotDePasse } from '../support/api';
import { jetonDeReinitialisation } from '../support/mailpit';

test('refuse un lien de réinitialisation invalide', async ({ page }) => {
  await page.goto('/reset-password?token=lien-invalide');

  await expect(page).toHaveURL(/\/login\?motif=lien-expire$/);
  await expect(
    page.getByText('Ce lien de réinitialisation est invalide ou a expiré.'),
  ).toBeVisible();
});

test('réinitialise le mot de passe par le lien reçu par courriel', async ({ page }) => {
  const compte = await creerCompteTemporaire('lecteur');

  await page.goto('/forgot-password');
  await page.getByLabel('Email').fill(compte.email);
  await page.getByRole('button', { name: 'Envoyer le lien' }).click();
  await expect(page.getByText('Si un compte existe pour cet email')).toBeVisible();

  const jeton = await jetonDeReinitialisation(compte.email);
  await page.goto(`/reset-password?token=${encodeURIComponent(jeton)}`);
  await page.getByLabel('Nouveau mot de passe').fill(nouveauMotDePasse());
  await page.getByRole('button', { name: 'Valider' }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: "Vue d'ensemble" })).toBeVisible();
});
