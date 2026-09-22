import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { NEVER, of, throwError } from 'rxjs';
import { RecommendationList, joinByAlert } from './recommendation-list';
import { AlertsService } from '../../../core/services/alerts.service';
import { RecommendationsService } from '../../../core/services/recommendations.service';
import { Alert } from '../../models/alert.model';
import { Recommendation } from '../../models/recommendation.model';
import { Site } from '../../models/site.model';

const SITES: Site[] = [
  {
    site_id: 'SITE001',
    site_name: 'Usine Nantes',
    site_type: 'industriel',
    location: 'Nantes',
    capacity_kw: 500,
    status: 'actif',
  },
  {
    site_id: 'SITE002',
    site_name: 'Bureau Lille',
    site_type: 'bureau',
    location: 'Lille',
    capacity_kw: 80,
    status: 'actif',
  },
];

function alerte(surcharges: Partial<Alert>): Alert {
  return {
    alert_id: 1,
    site_id: 'SITE001',
    timestamp: '2026-09-15T09:00:00Z',
    type: 'threshold',
    severity: 'high',
    message: 'Puissance appelée au-dessus de la capacité du site',
    value: 812.5,
    threshold: 720,
    metric: 'consumption_kw',
    prediction_id: null,
    ...surcharges,
  };
}

function reco(surcharges: Partial<Recommendation>): Recommendation {
  return {
    recommendation_id: 1,
    alert_id: 1,
    action: 'Ramener la puissance appelée sous le seuil contractuel',
    explanation: 'Seuil de consommation dépassé sur le site SITE001.',
    rule_reference: 'threshold-reduction-v1',
    created_at: '2026-09-15T09:05:00Z',
    ...surcharges,
  };
}

const ALERTES: Alert[] = [
  alerte({ alert_id: 1, site_id: 'SITE001', timestamp: '2026-09-15T09:00:00Z' }),
  alerte({
    alert_id: 2,
    site_id: 'SITE002',
    timestamp: '2026-09-15T11:00:00Z',
    severity: 'critical',
    type: 'spike',
    message: 'Variation brutale entre deux lectures consécutives',
  }),
  alerte({ alert_id: 3, site_id: 'SITE001', timestamp: '2026-09-15T10:00:00Z', severity: 'low' }),
];

const RECOMMANDATIONS: Recommendation[] = [
  reco({
    recommendation_id: 3,
    alert_id: 2,
    action: "Escalader à l'astreinte sous une heure",
    rule_reference: 'escalade-astreinte-v1',
  }),
  reco({ recommendation_id: 1, alert_id: 1 }),
  reco({
    recommendation_id: 2,
    alert_id: 2,
    action: 'Délester les équipements non prioritaires sur le créneau du pic',
    rule_reference: 'spike-delestage-v1',
  }),
  reco({ recommendation_id: 4, alert_id: 99, rule_reference: 'orpheline-v1' }),
];

function setup(
  alertsMock: { getAlerts: ReturnType<typeof vi.fn> },
  recosMock: { getRecommendations: ReturnType<typeof vi.fn> },
  inputs: Record<string, unknown> = {},
) {
  TestBed.configureTestingModule({
    imports: [RecommendationList],
    providers: [
      provideRouter([]),
      { provide: AlertsService, useValue: alertsMock },
      { provide: RecommendationsService, useValue: recosMock },
    ],
  });
  const fixture = TestBed.createComponent(RecommendationList);
  for (const [nom, valeur] of Object.entries(inputs)) {
    fixture.componentRef.setInput(nom, valeur);
  }
  return fixture;
}

function rendre(fixture: ComponentFixture<RecommendationList>) {
  fixture.detectChanges();
  fixture.detectChanges();
}

function texte(fixture: ComponentFixture<RecommendationList>): string {
  return (fixture.nativeElement as HTMLElement).textContent ?? '';
}

const recosOk = () => ({ getRecommendations: vi.fn().mockReturnValue(of(RECOMMANDATIONS)) });

describe('joinByAlert', () => {
  it('groupe par alerte, du plus récent au plus ancien, recommandations par identifiant', () => {
    const groupes = joinByAlert(ALERTES, RECOMMANDATIONS, new Map([['SITE001', 'Usine Nantes']]));

    expect(groupes.map((g) => g.alert.alert_id)).toEqual([2, 1]);
    expect(groupes[0].recommendations.map((r) => r.recommendation_id)).toEqual([2, 3]);
    expect(groupes[1].siteName).toBe('Usine Nantes');
    expect(groupes[0].siteName).toBe('SITE002');
  });

  it('ignore les alertes sans recommandation et les recommandations orphelines', () => {
    const groupes = joinByAlert(ALERTES, RECOMMANDATIONS, new Map());

    expect(groupes.some((g) => g.alert.alert_id === 3)).toBe(false);
    expect(groupes.flatMap((g) => g.recommendations).some((r) => r.alert_id === 99)).toBe(false);
  });
});

describe('RecommendationList', () => {
  it('charge alertes et recommandations puis affiche les groupes avec leur contexte', () => {
    const getAlerts = vi.fn().mockReturnValue(of(ALERTES));
    const fixture = setup({ getAlerts }, recosOk(), { sites: SITES });

    rendre(fixture);

    expect(getAlerts).toHaveBeenCalledWith({});
    expect(fixture.nativeElement.querySelectorAll('.reco-group').length).toBe(2);
    const contenu = texte(fixture);
    expect(contenu).toContain('Usine Nantes');
    expect(contenu).toContain('Bureau Lille');
    expect(contenu).toContain('Critique');
    expect(contenu).toContain('Pic de consommation');
    expect(contenu).toContain('Escalade astreinte');
    expect(contenu).toContain('Délester les équipements');
    expect(contenu).toContain('15/09/2026');
    expect(fixture.nativeElement.querySelector('a[href="/sites/SITE002"]')).not.toBeNull();
    expect(fixture.componentInstance.total()).toBe(3);
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it('filtre les alertes du site côté API et masque le lien vers le site', () => {
    const getAlerts = vi.fn().mockReturnValue(of(ALERTES.filter((a) => a.site_id === 'SITE001')));
    const fixture = setup({ getAlerts }, recosOk(), { siteId: 'SITE001', sites: SITES });

    rendre(fixture);

    expect(getAlerts).toHaveBeenCalledWith({ site_id: 'SITE001' });
    expect(fixture.nativeElement.querySelectorAll('.reco-group').length).toBe(1);
    expect(fixture.nativeElement.querySelector('a[href^="/sites/"]')).toBeNull();
  });

  it("ne garde que le groupe de l'alerte ciblée et le met en évidence", () => {
    const fixture = setup({ getAlerts: vi.fn().mockReturnValue(of(ALERTES)) }, recosOk(), {
      alertId: 2,
    });

    rendre(fixture);

    const groupes = fixture.nativeElement.querySelectorAll('.reco-group');
    expect(groupes.length).toBe(1);
    expect(groupes[0].classList.contains('reco-group--focus')).toBe(true);
    expect(groupes[0].id).toBe('alerte-2');
  });

  it("annonce l'absence de recommandation pour une alerte inconnue", () => {
    const fixture = setup({ getAlerts: vi.fn().mockReturnValue(of(ALERTES)) }, recosOk(), {
      alertId: 123,
    });

    rendre(fixture);

    expect(texte(fixture)).toContain('Aucune recommandation pour cette alerte.');
  });

  it("annonce l'absence de recommandation pour le site consulté", () => {
    const fixture = setup(
      { getAlerts: vi.fn().mockReturnValue(of([])) },
      { getRecommendations: vi.fn().mockReturnValue(of([])) },
      { siteId: 'SITE001' },
    );

    rendre(fixture);

    expect(texte(fixture)).toContain('Aucune recommandation pour ce site.');
  });

  it("signale l'indisponibilité et n'affiche aucun groupe si un des deux appels échoue", () => {
    const fixture = setup(
      { getAlerts: vi.fn().mockReturnValue(of(ALERTES)) },
      { getRecommendations: vi.fn().mockReturnValue(throwError(() => new Error('nope'))) },
    );

    rendre(fixture);

    expect(fixture.componentInstance.error()).not.toBeNull();
    expect(fixture.componentInstance.groups()).toEqual([]);
    expect(texte(fixture)).toContain('Recommandations indisponibles');
    expect(fixture.nativeElement.querySelectorAll('.reco-group').length).toBe(0);
  });

  it('annonce le chargement tant que la réponse ne vient pas', () => {
    const fixture = setup(
      { getAlerts: vi.fn().mockReturnValue(NEVER) },
      { getRecommendations: vi.fn().mockReturnValue(NEVER) },
    );

    rendre(fixture);

    expect(fixture.componentInstance.loading()).toBe(true);
    expect(texte(fixture)).toContain('Chargement des recommandations');
  });

  it('recharge les deux flux à la demande', () => {
    const getAlerts = vi.fn().mockReturnValue(of(ALERTES));
    const recos = recosOk();
    const fixture = setup({ getAlerts }, recos);
    rendre(fixture);

    fixture.componentInstance.reload();
    rendre(fixture);

    expect(getAlerts).toHaveBeenCalledTimes(2);
    expect(recos.getRecommendations).toHaveBeenCalledTimes(2);
  });
});
