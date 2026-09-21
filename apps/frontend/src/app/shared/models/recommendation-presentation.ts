import { BadgeTone } from '../components/ui/badge/badge';

// Contrainte : une règle dont le sens change reçoit un suffixe -v2 côté backend (ADR 0006) ;
// une référence inconnue s'affiche donc telle quelle plutôt que de casser la vue.
const LIBELLE_PAR_REGLE: Record<string, string> = {
  'spike-delestage-v1': 'Délestage',
  'threshold-reduction-v1': 'Réduction de puissance',
  'outage-secours-v1': 'Alimentation de secours',
  'sensor-maintenance-v1': 'Maintenance capteur',
  'anomaly-verification-v1': 'Vérification',
  'escalade-astreinte-v1': 'Escalade astreinte',
  'contrat-puissance-v1': 'Contrat de puissance',
};

const REGLE_ESCALADE = 'escalade-astreinte-v1';

export function libelleRegle(reference: string): string {
  return LIBELLE_PAR_REGLE[reference] ?? reference;
}

export function tonRegle(reference: string): BadgeTone {
  return reference === REGLE_ESCALADE ? 'critical' : 'neutral';
}
