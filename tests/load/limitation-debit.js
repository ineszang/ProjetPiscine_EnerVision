// Vérifie par le proxy que la limitation de nginx tient : au-delà de 20 requêtes par seconde et
// de la rafale de 40, une même adresse doit recevoir des 429, et jamais une erreur serveur.
import { check } from 'k6';
import http from 'k6/http';
import { Counter } from 'k6/metrics';

import { PROXY_URL, STATISTIQUES } from './lib/config.js';
import { rapport } from './lib/rapport.js';

const limitees = new Counter('reponses_limitees');

http.setResponseCallback(http.expectedStatuses(200, 429));

export const options = {
  insecureSkipTLSVerify: true,
  scenarios: {
    rafale: {
      executor: 'constant-arrival-rate',
      rate: 80,
      timeUnit: '1s',
      duration: '15s',
      preAllocatedVUs: 20,
      maxVUs: 80,
    },
  },
  thresholds: {
    reponses_limitees: ['count>0'],
    http_req_failed: ['rate<0.01'],
  },
  summaryTrendStats: STATISTIQUES,
};

export default function () {
  const reponse = http.get(`${PROXY_URL}/api/v1/health/live`, { tags: { name: 'health_live' } });
  if (reponse.status === 429) {
    limitees.add(1);
  }
  check(reponse, { 'servie ou limitée, jamais en erreur': (r) => [200, 429].includes(r.status) });
}

export function handleSummary(data) {
  return rapport('limitation-debit', data);
}
