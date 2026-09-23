import { expect, request } from '@playwright/test';

import { MAILPIT_URL } from './environnement';

interface Recherche {
  messages: { ID: string }[];
}

// Le courriel part en tâche de fond après la réponse de l'API : on l'attend dans Mailpit.
export async function jetonDeReinitialisation(email: string): Promise<string> {
  const mailpit = await request.newContext({ baseURL: MAILPIT_URL });
  try {
    let identifiant = '';
    await expect
      .poll(
        async () => {
          const reponse = await mailpit.get('/api/v1/search', { params: { query: `to:${email}` } });
          const { messages } = (await reponse.json()) as Recherche;
          identifiant = messages[0]?.ID ?? '';
          return identifiant;
        },
        { message: `aucun courriel reçu pour ${email}`, timeout: 15_000 },
      )
      .not.toBe('');

    const message = (await (await mailpit.get(`/api/v1/message/${identifiant}`)).json()) as {
      Text: string;
    };
    const jeton = /reset-password\?token=([^\s"<>&]+)/.exec(message.Text)?.[1];
    if (!jeton) {
      throw new Error('lien de réinitialisation introuvable dans le courriel');
    }
    return decodeURIComponent(jeton);
  } finally {
    await mailpit.dispose();
  }
}
