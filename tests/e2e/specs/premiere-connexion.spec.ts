import { expect, test } from '@playwright/test';

import { creerCompteTemporaire, nouveauMotDePasse } from '../support/api';
import { seConnecter } from '../support/session';

test('impose le changement du mot de passe temporaire avant le tableau de bord', async ({
  page,
}) => {
  const compte = await creerCompteTemporaire('lecteur');

  await seConnecter(page, compte);
  await expect(page).toHaveURL(/\/change-password$/);
  await expect(page.getByRole('heading', { name: 'Nouveau mot de passe' })).toBeVisible();

  await expect(page.getByLabel('Mot de passe actuel')).toHaveCount(0);
  await page.getByLabel('Nouveau mot de passe').fill(nouveauMotDePasse());
  await page.getByRole('button', { name: 'Valider' }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: "Vue d'ensemble" })).toBeVisible();
});
