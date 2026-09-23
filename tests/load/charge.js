// Charge nominale : 50 utilisateurs simultanés. 40 gardent le tableau de bord ouvert, qui
// interroge l'API au rythme du frontend ; 10 explorent les sites.
import { sleep } from 'k6';

import { auHasard, consulterSite, lire, preparer } from './lib/api.js';
import { SEUILS, STATISTIQUES } from './lib/config.js';
import { rapport } from './lib/rapport.js';

const paliers = (cible) => [
  { duration: '2m', target: cible },
  { duration: '5m', target: cible },
  { duration: '1m', target: 0 },
];

export const options = {
  insecureSkipTLSVerify: true,
  scenarios: {
    tableau_de_bord: {
      executor: 'ramping-vus',
      stages: paliers(40),
      exec: 'tableauDeBord',
      gracefulRampDown: '30s',
    },
    exploration: {
      executor: 'ramping-vus',
      stages: paliers(10),
      exec: 'exploration',
      gracefulRampDown: '30s',
    },
  },
  thresholds: SEUILS,
  summaryTrendStats: STATISTIQUES,
};

export const setup = preparer;

// Une itération vaut une minute d'écran ouvert : `/stats/summary` toutes les 10 s, les alertes
// toutes les 60 s, les prévisions une fois (dashboard.ts, alert-feed.ts).
export function tableauDeBord(data) {
  lire('/predictions', 'predictions', data.jeton);
  lire('/alerts', 'alerts', data.jeton);
  for (let i = 0; i < 6; i += 1) {
    lire('/stats/summary', 'stats_summary', data.jeton);
    sleep(10);
  }
}

export function exploration(data) {
  lire('/sites', 'sites', data.jeton);
  consulterSite(auHasard(data.sites), data.jeton);
  sleep(3 + Math.random() * 5);
}

export function handleSummary(data) {
  return rapport('charge', data);
}
