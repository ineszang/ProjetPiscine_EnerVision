import { request } from '@playwright/test';

import { comptes, type Compte } from './comptes';
import { API_URL } from './environnement';

// Crée par l'API un compte neuf, encore sur son mot de passe temporaire. Un compte par appel :
// un nouvel essai après échec ne retombe jamais sur un compte déjà activé.
export async function creerCompteTemporaire(role: 'lecteur' | 'operateur'): Promise<Compte> {
  const api = await request.newContext({ baseURL: API_URL, ignoreHTTPSErrors: true });
  try {
    const connexion = await api.post('auth/login', { data: comptes.admin });
    if (!connexion.ok()) {
      throw new Error(`Connexion administrateur refusée : ${connexion.status()}`);
    }
    const { access_token: jeton } = (await connexion.json()) as { access_token: string };

    const email = `e2e-${role}-${Date.now()}@enervision.fr`;
    const creation = await api.post('users', {
      data: { email, role },
      headers: { Authorization: `Bearer ${jeton}` },
    });
    if (!creation.ok()) {
      throw new Error(`Création du compte refusée : ${creation.status()}`);
    }
    const { temporary_password: password } = (await creation.json()) as {
      temporary_password: string;
    };
    return { email, password };
  } finally {
    await api.dispose();
  }
}

export function nouveauMotDePasse(): string {
  return `E2e-${Math.random().toString(36).slice(2, 14)}-Aa1!`;
}
