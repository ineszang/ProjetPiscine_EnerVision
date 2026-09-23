import { check, fail } from 'k6';
import http from 'k6/http';

import { API, COMPTE } from './config.js';

export function connecter() {
  if (!COMPTE.email || !COMPTE.password) {
    fail('K6_EMAIL et K6_PASSWORD désignent un compte lecteur déjà activé');
  }
  const reponse = http.post(`${API}/auth/login`, JSON.stringify(COMPTE), {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'auth_login', type: 'auth' },
  });
  if (!check(reponse, { 'connexion acceptée': (r) => r.status === 200 })) {
    fail(`connexion refusée : ${reponse.status} ${reponse.body}`);
  }
  return reponse.json('access_token');
}

// Jeton propre à chaque VU, repris sur un 401 : un tir plus long que le TTL du jeton (15 min)
// ne doit pas finir en erreurs. Jamais de refresh, dont la rotation révoquerait la session.
let jetonDuVu = null;

export function lire(chemin, nom, jetonInitial) {
  const envoyer = () =>
    http.get(`${API}${chemin}`, {
      headers: { Authorization: `Bearer ${jetonDuVu || jetonInitial}` },
      tags: { name: nom, type: 'lecture' },
    });
  let reponse = envoyer();
  if (reponse.status === 401) {
    jetonDuVu = connecter();
    reponse = envoyer();
  }
  check(reponse, { [`${nom} répond 200`]: (r) => r.status === 200 });
  return reponse;
}

export function preparer() {
  const jeton = connecter();
  const sites = lire('/sites', 'sites', jeton).json();
  if (!Array.isArray(sites) || sites.length === 0) {
    fail('aucun site en base : semer db/seeds/demo.sql ou importer des relevés avant le tir');
  }
  return { jeton, sites: sites.map((site) => site.site_id) };
}

export function auHasard(liste) {
  return liste[Math.floor(Math.random() * liste.length)];
}

// Même fenêtre que le détail d'un site dans le frontend : les 24 heures qui précèdent sa
// dernière mesure, pas celles qui précèdent l'instant présent.
export function consulterSite(siteId, jeton) {
  lire(`/sites/${siteId}`, 'site', jeton);
  const courant = lire(`/sites/${siteId}/current`, 'site_current', jeton);
  const horodatage = courant.status === 200 ? courant.json('timestamp') : null;
  const fin = horodatage ? new Date(horodatage) : new Date();
  const debut = new Date(fin.getTime() - 24 * 3600 * 1000);
  const fenetre = `start=${encodeURIComponent(debut.toISOString())}&end=${encodeURIComponent(fin.toISOString())}`;
  lire(`/readings?site_id=${siteId}&${fenetre}`, 'readings', jeton);
  lire(`/recommendations?site_id=${siteId}`, 'recommendations', jeton);
}
