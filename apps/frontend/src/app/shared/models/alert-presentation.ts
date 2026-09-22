import { BadgeTone } from '../components/ui/badge/badge';
import { AlertMetric, AlertSeverity, AlertType } from './alert.model';

// Pourquoi : `low` en neutre plutôt qu'en vert, une alerte faible reste une alerte ; le vert se
// lisait comme « tout va bien » à côté des rouges.
export const TON_PAR_SEVERITE: Record<AlertSeverity, BadgeTone> = {
  low: 'neutral',
  medium: 'warning',
  high: 'danger',
  critical: 'critical',
};

export const LIBELLE_PAR_SEVERITE: Record<AlertSeverity, string> = {
  low: 'Faible',
  medium: 'Moyenne',
  high: 'Élevée',
  critical: 'Critique',
};

export const LIBELLE_PAR_TYPE: Record<AlertType, string> = {
  spike: 'Pic de consommation',
  threshold: 'Seuil dépassé',
  anomaly: 'Anomalie',
  outage: 'Coupure',
  sensor: 'Capteur',
};

export const UNITE_PAR_METRIQUE: Record<AlertMetric, string> = {
  consumption_kw: 'kW',
  consumption_kwh: 'kWh',
};

export const SEVERITES: readonly AlertSeverity[] = ['low', 'medium', 'high', 'critical'];

export const TYPES_ALERTE: readonly AlertType[] = [
  'spike',
  'threshold',
  'anomaly',
  'outage',
  'sensor',
];
