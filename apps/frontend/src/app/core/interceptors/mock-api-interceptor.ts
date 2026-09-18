import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { STATS_SUMMARY_FIXTURE } from '../mocks/stats-summary.fixture';
import { ALERTS_FIXTURE } from '../mocks/alerts.fixture';

function withJitter(base: typeof STATS_SUMMARY_FIXTURE) {
  const jitter = () => (Math.random() - 0.5) * 40;
  const totalConsumption = Math.max(0, base.total_consumption_kw + jitter());

  return {
    ...base,
    timestamp: new Date().toISOString(),
    total_consumption_kw: Math.round(totalConsumption * 100) / 100,
    average_load_percent: Math.round((totalConsumption / base.total_capacity_kw) * 1000) / 10,
  };
}

export const mockApiInterceptor: HttpInterceptorFn = (req, next) => {
  if (!environment.useMockFixtures) {
    return next(req);
  }
  if (req.url.endsWith(`${environment.apiUrl}/stats/summary`)) {
    return of(new HttpResponse({ status: 200, body: withJitter(STATS_SUMMARY_FIXTURE) }));
  }
  if (req.url.endsWith(`${environment.apiUrl}/alerts`)) {
    return of(new HttpResponse({ status: 200, body: ALERTS_FIXTURE }));
  }
  // Volontairement jamais mocké, contrairement à `stats`/`alerts` : les prévisions sont servies
  // par l'API réelle dès maintenant (au même titre que `/auth/*`, déjà toujours réel).
  return next(req);
};
