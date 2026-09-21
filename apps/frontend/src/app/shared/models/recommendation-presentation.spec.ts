import { libelleRegle, tonRegle } from './recommendation-presentation';

describe('recommendation-presentation', () => {
  it('traduit les sept règles connues du moteur', () => {
    expect(libelleRegle('spike-delestage-v1')).toBe('Délestage');
    expect(libelleRegle('threshold-reduction-v1')).toBe('Réduction de puissance');
    expect(libelleRegle('outage-secours-v1')).toBe('Alimentation de secours');
    expect(libelleRegle('sensor-maintenance-v1')).toBe('Maintenance capteur');
    expect(libelleRegle('anomaly-verification-v1')).toBe('Vérification');
    expect(libelleRegle('escalade-astreinte-v1')).toBe('Escalade astreinte');
    expect(libelleRegle('contrat-puissance-v1')).toBe('Contrat de puissance');
  });

  it('affiche telle quelle une référence de règle inconnue', () => {
    expect(libelleRegle('spike-delestage-v2')).toBe('spike-delestage-v2');
  });

  it("réserve le ton critique à l'escalade vers l'astreinte", () => {
    expect(tonRegle('escalade-astreinte-v1')).toBe('critical');
    expect(tonRegle('spike-delestage-v1')).toBe('neutral');
    expect(tonRegle('inconnue-v9')).toBe('neutral');
  });
});
