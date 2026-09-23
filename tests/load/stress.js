// Monte le débit jusqu'à la rupture pour situer la limite de l'API. S'arrête de lui-même au-delà
// de 10 % d'erreurs : le but est de trouver le point de rupture, pas de s'y maintenir.
import { auHasard, consulterSite, lire, preparer } from './lib/api.js';
import { STATISTIQUES } from './lib/config.js';
import { rapport } from './lib/rapport.js';

export const options = {
  insecureSkipTLSVerify: true,
  scenarios: {
    stress: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 400,
      stages: [
        { duration: '2m', target: 25 },
        { duration: '2m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '2m', target: 200 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: true, delayAbortEval: '30s' }],
    'http_req_duration{type:lecture}': ['p(95)<2000'],
  },
  summaryTrendStats: STATISTIQUES,
};

export const setup = preparer;

export default function (data) {
  if (Math.random() < 0.6) {
    lire('/stats/summary', 'stats_summary', data.jeton);
  } else {
    consulterSite(auHasard(data.sites), data.jeton);
  }
}

export function handleSummary(data) {
  return rapport('stress', data);
}
