export const BASE_URL = __ENV.K6_BASE_URL || 'http://backend:8000';
export const API = `${BASE_URL}/api/v1`;
export const PROXY_URL = __ENV.K6_PROXY_URL || 'https://proxy';

export const COMPTE = {
  email: __ENV.K6_EMAIL,
  password: __ENV.K6_PASSWORD,
};

// Seuils posés par l'ADR 0015, faute d'exigence chiffrée dans le cahier des charges.
export const SEUILS = {
  http_req_failed: ['rate<0.01'],
  checks: ['rate>0.99'],
  'http_req_duration{type:lecture}': ['p(95)<500', 'p(99)<1000'],
  'http_req_duration{name:stats_summary}': ['p(95)<500'],
  'http_req_duration{name:readings}': ['p(95)<800'],
};

export const STATISTIQUES = ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'];
