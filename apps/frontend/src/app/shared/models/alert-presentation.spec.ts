import {
  LIBELLE_PAR_SEVERITE,
  LIBELLE_PAR_TYPE,
  SEVERITES,
  TON_PAR_SEVERITE,
  TYPES_ALERTE,
  UNITE_PAR_METRIQUE,
} from './alert-presentation';

describe('alert-presentation', () => {
  it('distingue le ton des sévérités high et critical', () => {
    expect(TON_PAR_SEVERITE.high).toBe('danger');
    expect(TON_PAR_SEVERITE.critical).toBe('critical');
    expect(TON_PAR_SEVERITE.high).not.toBe(TON_PAR_SEVERITE.critical);
  });

  it("n'affiche pas une alerte faible avec le ton de succès", () => {
    expect(TON_PAR_SEVERITE.low).toBe('neutral');
    expect(TON_PAR_SEVERITE.medium).toBe('warning');
  });

  it('donne un libellé français à chaque sévérité et à chaque type', () => {
    for (const severite of SEVERITES) {
      expect(LIBELLE_PAR_SEVERITE[severite]).toBeTruthy();
    }
    for (const type of TYPES_ALERTE) {
      expect(LIBELLE_PAR_TYPE[type]).toBeTruthy();
    }
    expect(SEVERITES.length).toBe(4);
    expect(TYPES_ALERTE.length).toBe(5);
  });

  it('associe une unité à chaque métrique du contrat', () => {
    expect(UNITE_PAR_METRIQUE.consumption_kw).toBe('kW');
    expect(UNITE_PAR_METRIQUE.consumption_kwh).toBe('kWh');
  });
});
