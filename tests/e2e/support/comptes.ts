import { readFileSync } from 'node:fs';

export interface Compte {
  email: string;
  password: string;
}

interface ComptesDeTest {
  admin: Compte;
  lecteur: Compte;
  operateur: Compte;
}

function lireComptes(): ComptesDeTest {
  const chemin = process.env.E2E_COMPTES;
  if (!chemin) {
    throw new Error('E2E_COMPTES doit désigner le JSON écrit par scripts/comptes-test.sh');
  }
  return JSON.parse(readFileSync(chemin, 'utf-8')) as ComptesDeTest;
}

export const comptes = lireComptes();
