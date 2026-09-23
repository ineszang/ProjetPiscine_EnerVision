import { sleep } from 'k6';

import { auHasard, consulterSite, lire, preparer } from './lib/api.js';
import { SEUILS, STATISTIQUES } from './lib/config.js';
import { rapport } from './lib/rapport.js';

export const options = {
  insecureSkipTLSVerify: true,
  scenarios: {
    smoke: { executor: 'constant-vus', vus: 2, duration: '1m' },
  },
  thresholds: SEUILS,
  summaryTrendStats: STATISTIQUES,
};

export const setup = preparer;

export default function (data) {
  lire('/stats/summary', 'stats_summary', data.jeton);
  lire('/predictions', 'predictions', data.jeton);
  lire('/alerts', 'alerts', data.jeton);
  lire('/sites', 'sites', data.jeton);
  consulterSite(auHasard(data.sites), data.jeton);
  sleep(1);
}

export function handleSummary(data) {
  return rapport('smoke', data);
}
