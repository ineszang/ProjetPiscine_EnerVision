import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { AlertFeed } from './alert-feed';
import { AlertsService } from '../../../core/services/alerts.service';
import { SitesService } from '../../../core/services/sites.service';
import { Alert } from '../../models/alert.model';
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
];

function alerte(surcharges: Partial<Alert> = {}): Alert {
  return {
    alert_id: 1,
    site_id: 'SITE001',
    timestamp: '2026-09-15T11:12:00Z',
    type: 'spike',
    severity: 'critical',
    message: 'Variation brutale entre deux lectures consécutives',
    value: 812.5,
    threshold: 400,
    metric: 'consumption_kw',
    prediction_id: null,
    ...surcharges,
  };
}

function setup(
  alertsMock: { getAlerts: ReturnType<typeof vi.fn> },
  sitesMock: { getSites: ReturnType<typeof vi.fn> } = {
    getSites: vi.fn().mockReturnValue(of(SITES)),
  },
) {
  TestBed.configureTestingModule({
    imports: [AlertFeed],
    providers: [
      { provide: AlertsService, useValue: alertsMock },
      { provide: SitesService, useValue: sitesMock },
    ],
  });
  return TestBed.createComponent(AlertFeed);
}

function premierChargement(fixture: ComponentFixture<AlertFeed>) {
  fixture.detectChanges();
  vi.advanceTimersByTime(1);
  fixture.detectChanges();
}

function texte(fixture: ComponentFixture<AlertFeed>): string {
  return (fixture.nativeElement as HTMLElement).textContent ?? '';
}

function choisir(fixture: ComponentFixture<AlertFeed>, testId: string, value: string) {
  const select = fixture.nativeElement.querySelector(
    `[data-testid="${testId}"]`,
  ) as HTMLSelectElement;
  select.value = value;
  select.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  vi.advanceTimersByTime(1);
  fixture.detectChanges();
}

describe('AlertFeed', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('charge les alertes au démarrage sans filtre et les affiche avec leur contexte', () => {
    const getAlerts = vi.fn().mockReturnValue(of([alerte()]));
    const fixture = setup({ getAlerts });

    premierChargement(fixture);

    expect(getAlerts).toHaveBeenCalledTimes(1);
    expect(getAlerts.mock.calls[0][0]).toEqual({});
    const contenu = texte(fixture);
    expect(contenu).toContain('Usine Nantes');
    expect(contenu).toContain('Critique');
    expect(contenu).toContain('Pic de consommation');
    expect(contenu).toContain('15/09/2026');
    expect(contenu).toContain('812.5 kW');
    expect(contenu).toContain('seuil 400 kW');
    expect(fixture.nativeElement.querySelector('ev-icon svg')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.alert-feed__item--critical')).not.toBeNull();
  });

  it('annonce le chargement avant la première réponse', () => {
    const fixture = setup({ getAlerts: vi.fn().mockReturnValue(of([])) });

    fixture.detectChanges();

    expect(fixture.componentInstance.loading()).toBe(true);
    expect(texte(fixture)).toContain('Chargement des alertes');
  });

  it("annonce l'absence d'alerte pour les critères choisis", () => {
    const fixture = setup({ getAlerts: vi.fn().mockReturnValue(of([])) });

    premierChargement(fixture);

    expect(texte(fixture)).toContain('Aucune alerte pour ces critères.');
    expect(fixture.nativeElement.querySelectorAll('li').length).toBe(0);
  });

  it('relance la requête avec la sévérité choisie et revient à la première page', () => {
    const getAlerts = vi.fn().mockReturnValue(of([alerte()]));
    const fixture = setup({ getAlerts });
    premierChargement(fixture);
    fixture.componentInstance.showMore();

    choisir(fixture, 'severity-filter', 'high');

    expect(getAlerts).toHaveBeenCalledTimes(2);
    expect(getAlerts.mock.calls[1][0]).toEqual({ severity: 'high' });
    expect(fixture.componentInstance.visibleCount()).toBe(10);
  });

  it('relance la requête avec le site choisi dans le filtre', () => {
    const getAlerts = vi.fn().mockReturnValue(of([]));
    const fixture = setup({ getAlerts });
    premierChargement(fixture);

    choisir(fixture, 'site-filter', 'SITE001');

    expect(getAlerts.mock.calls[1][0]).toEqual({ site_id: 'SITE001' });
  });

  it('masque le filtre site et force site_id quand le parent fixe le site', () => {
    const getAlerts = vi.fn().mockReturnValue(of([]));
    const fixture = setup({ getAlerts });
    fixture.componentRef.setInput('siteId', 'SITE001');

    premierChargement(fixture);

    expect(getAlerts.mock.calls[0][0]).toEqual({ site_id: 'SITE001' });
    expect(fixture.nativeElement.querySelector('[data-testid="site-filter"]')).toBeNull();
    expect(fixture.nativeElement.querySelector('[data-testid="severity-filter"]')).not.toBeNull();
  });

  it("signale l'indisponibilité en gardant la liste, puis repart au rafraîchissement suivant", () => {
    const getAlerts = vi
      .fn()
      .mockReturnValueOnce(of([alerte()]))
      .mockReturnValueOnce(throwError(() => new Error('API injoignable')))
      .mockReturnValue(of([alerte(), alerte({ alert_id: 2 })]));
    const fixture = setup({ getAlerts });
    premierChargement(fixture);

    vi.advanceTimersByTime(60_000);
    fixture.detectChanges();

    expect(getAlerts).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.error()).not.toBeNull();
    expect(fixture.componentInstance.alerts().length).toBe(1);
    expect(texte(fixture)).toContain('Alertes indisponibles');

    vi.advanceTimersByTime(60_000);
    fixture.detectChanges();

    expect(getAlerts).toHaveBeenCalledTimes(3);
    expect(fixture.componentInstance.error()).toBeNull();
    expect(fixture.componentInstance.alerts().length).toBe(2);
  });

  it('pagine côté client par dix et dévoile le reste à la demande', () => {
    const alertes = Array.from({ length: 25 }, (_, i) => alerte({ alert_id: i + 1 }));
    const fixture = setup({ getAlerts: vi.fn().mockReturnValue(of(alertes)) });
    premierChargement(fixture);

    expect(fixture.nativeElement.querySelectorAll('li').length).toBe(10);
    expect(texte(fixture)).toContain('Afficher plus (15 restantes)');

    fixture.nativeElement.querySelector('[data-testid="show-more"]').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('li').length).toBe(20);

    fixture.nativeElement.querySelector('[data-testid="show-more"]').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('li').length).toBe(25);
    expect(fixture.nativeElement.querySelector('[data-testid="show-more"]')).toBeNull();
  });

  it("replie sur l'identifiant quand le site est inconnu ou que la liste des sites échoue", () => {
    const fixture = setup(
      { getAlerts: vi.fn().mockReturnValue(of([alerte({ site_id: 'SITE999' })])) },
      { getSites: vi.fn().mockReturnValue(throwError(() => new Error('nope'))) },
    );

    premierChargement(fixture);

    expect(texte(fixture)).toContain('SITE999');
  });

  it("n'affiche pas de mesure pour une alerte sans valeur", () => {
    const fixture = setup({
      getAlerts: vi
        .fn()
        .mockReturnValue(
          of([alerte({ type: 'outage', value: null, threshold: null, metric: null })]),
        ),
    });

    premierChargement(fixture);

    expect(fixture.nativeElement.querySelector('.alert-feed__values')).toBeNull();
    expect(texte(fixture)).toContain('Coupure');
  });
});
