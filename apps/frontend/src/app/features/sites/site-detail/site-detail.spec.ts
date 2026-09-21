import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { SiteDetail } from './site-detail';
import { SitesService } from '../../../core/services/sites.service';
import { ReadingsService } from '../../../core/services/readings.service';
import { AlertsService } from '../../../core/services/alerts.service';
import { RecommendationsService } from '../../../core/services/recommendations.service';

const SITE = {
  site_id: 'SITE001',
  site_name: 'Site 1',
  site_type: 'industriel',
  location: 'Nantes',
  capacity_kw: 500,
  status: 'actif',
};

const CURRENT_COMPLET = {
  timestamp: '2026-09-17T10:00:00Z',
  site_id: 'SITE001',
  site_type: 'industriel',
  consumption_kw: 120,
  consumption_kwh: null,
  voltage_v: 230,
  current_a: 12,
  power_factor: 0.95,
  temperature_celsius: 22,
  humidity_percent: 55,
  null_reasons: [] as string[],
  data_quality: 'good' as const,
};

const SANS_MESURE = {
  ...CURRENT_COMPLET,
  timestamp: null,
  consumption_kw: null,
  voltage_v: null,
  current_a: null,
  power_factor: null,
  temperature_celsius: null,
  humidity_percent: null,
  data_quality: 'critical' as const,
};

const LECTURE = {
  reading_id: 1,
  site_id: 'SITE001',
  timestamp: '2026-09-17T09:00:00Z',
  source: 'api_history' as const,
  consumption_kw: 118,
  consumption_kwh: null,
  consumption_euros: null,
  voltage_v: 230,
  current_a: 12,
  power_factor: 0.95,
  temperature_celsius: 22,
  humidity_percent: 55,
  solar_irradiance_wm2: null,
  is_working_hours: true,
  data_quality: 'good' as const,
  null_reasons: null,
  imputed_values: null,
  imputation_method: null,
};

function setup(
  siteId: string,
  sitesMock: Partial<SitesService>,
  readingsMock: Partial<ReadingsService>,
) {
  const paramMap = new BehaviorSubject(convertToParamMap({ siteId }));
  const getAlerts = vi.fn().mockReturnValue(of([]));
  TestBed.configureTestingModule({
    imports: [SiteDetail],
    providers: [
      provideRouter([]),
      { provide: ActivatedRoute, useValue: { paramMap } },
      { provide: SitesService, useValue: sitesMock },
      { provide: ReadingsService, useValue: readingsMock },
      { provide: AlertsService, useValue: { getAlerts } },
      {
        provide: RecommendationsService,
        useValue: { getRecommendations: vi.fn().mockReturnValue(of([])) },
      },
    ],
  });
  return { fixture: TestBed.createComponent(SiteDetail), paramMap, getAlerts };
}

describe('SiteDetail', () => {
  it('charge le site, la mesure courante et son historique au démarrage', () => {
    const { fixture } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(of(SITE)),
        getCurrent: vi.fn().mockReturnValue(of(CURRENT_COMPLET)),
      },
      { getHistory: vi.fn().mockReturnValue(of([LECTURE])) },
    );

    fixture.detectChanges();

    expect(fixture.componentInstance.site()?.site_id).toBe('SITE001');
    expect(fixture.componentInstance.current()?.consumption_kw).toBe(120);
    expect(fixture.componentInstance.history().length).toBe(1);
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it("signale l'indisponibilité quand un des appels échoue", () => {
    const { fixture } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(throwError(() => new Error('nope'))),
        getCurrent: vi.fn().mockReturnValue(of(CURRENT_COMPLET)),
      },
      { getHistory: vi.fn().mockReturnValue(of([])) },
    );

    fixture.detectChanges();

    expect(fixture.componentInstance.error()).not.toBeNull();
    expect(fixture.componentInstance.site()).toBeNull();
  });

  it('efface les données du site précédent quand le chargement du suivant échoue', () => {
    const getSite = vi
      .fn()
      .mockReturnValueOnce(of(SITE))
      .mockReturnValueOnce(throwError(() => new Error('404')));
    const { fixture, paramMap } = setup(
      'SITE001',
      { getSite, getCurrent: vi.fn().mockReturnValue(of(CURRENT_COMPLET)) },
      { getHistory: vi.fn().mockReturnValue(of([LECTURE])) },
    );

    fixture.detectChanges();
    expect(fixture.componentInstance.site()?.site_id).toBe('SITE001');

    paramMap.next(convertToParamMap({ siteId: 'SITE002' }));
    fixture.detectChanges();

    expect(fixture.componentInstance.error()).not.toBeNull();
    expect(fixture.componentInstance.site()).toBeNull();
    expect(fixture.componentInstance.current()).toBeNull();
    expect(fixture.componentInstance.history()).toEqual([]);
    expect(fixture.nativeElement.textContent).not.toContain('Site 1');
  });

  it('interroge le site et sa mesure courante en parallèle', () => {
    const getSite = vi.fn().mockReturnValue(of(SITE));
    const getCurrent = vi.fn().mockReturnValue(of(CURRENT_COMPLET));
    const { fixture } = setup(
      'SITE001',
      { getSite, getCurrent },
      { getHistory: vi.fn().mockReturnValue(of([])) },
    );

    fixture.detectChanges();

    expect(getSite).toHaveBeenCalledWith('SITE001');
    expect(getCurrent).toHaveBeenCalledWith('SITE001');
  });

  it('signale la panne du capteur de consommation au lieu de tracer une jauge à zéro', () => {
    const sansConsommation = {
      ...CURRENT_COMPLET,
      consumption_kw: null,
      null_reasons: ['consumption_sensor_failure'],
      data_quality: 'partial' as const,
    };
    const { fixture } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(of(SITE)),
        getCurrent: vi.fn().mockReturnValue(of(sansConsommation)),
      },
      { getHistory: vi.fn().mockReturnValue(of([LECTURE])) },
    );

    fixture.detectChanges();

    expect(fixture.componentInstance.consumptionKw()).toBeNull();
    expect(fixture.componentInstance.consumptionReason()).toBe('capteur de consommation en panne');
    expect(fixture.nativeElement.querySelector('app-consumption-gauge')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Consommation indisponible');
  });

  it('trace la jauge pour une consommation nulle réellement mesurée', () => {
    const { fixture } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(of(SITE)),
        getCurrent: vi.fn().mockReturnValue(of({ ...CURRENT_COMPLET, consumption_kw: 0 })),
      },
      { getHistory: vi.fn().mockReturnValue(of([LECTURE])) },
    );

    fixture.detectChanges();

    expect(fixture.componentInstance.consumptionLabel()).toBe('0.0 kW');
    expect(fixture.nativeElement.querySelector('app-consumption-gauge')).not.toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Consommation indisponible');
  });

  it('affiche explicitement les champs null avec leur raison plutôt que de les masquer', () => {
    const partielle = {
      ...CURRENT_COMPLET,
      voltage_v: null,
      current_a: null,
      power_factor: null,
      null_reasons: ['electrical_sensor_failure'],
      data_quality: 'partial' as const,
    };
    const { fixture } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(of(SITE)),
        getCurrent: vi.fn().mockReturnValue(of(partielle)),
      },
      { getHistory: vi.fn().mockReturnValue(of([LECTURE])) },
    );

    fixture.detectChanges();

    const tension = fixture.componentInstance.metrics().find((m) => m.key === 'voltage_v');
    expect(tension?.value).toBeNull();
    expect(tension?.reason).toBe('capteur électrique en panne');

    const texte = fixture.nativeElement.textContent;
    expect(texte).toContain('Indisponible');
    expect(texte).toContain('capteur électrique en panne');
    expect(texte).toContain('Données partielles');
  });

  it('recharge les données quand le paramètre de route siteId change', () => {
    const getSite = vi.fn().mockReturnValue(of(SITE));
    const { fixture, paramMap } = setup(
      'SITE001',
      { getSite, getCurrent: vi.fn().mockReturnValue(of(CURRENT_COMPLET)) },
      { getHistory: vi.fn().mockReturnValue(of([])) },
    );

    fixture.detectChanges();
    paramMap.next(convertToParamMap({ siteId: 'SITE002' }));
    fixture.detectChanges();

    expect(getSite).toHaveBeenCalledWith('SITE002');
  });

  it("ancre la fenêtre d'historique sur la dernière mesure connue plutôt que sur l'horloge", () => {
    const getHistory = vi.fn().mockReturnValue(of([]));
    const { fixture } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(of(SITE)),
        getCurrent: vi.fn().mockReturnValue(of(CURRENT_COMPLET)),
      },
      { getHistory },
    );

    fixture.detectChanges();

    expect(getHistory).toHaveBeenCalledWith(
      'SITE001',
      '2026-09-16T10:00:00.000Z',
      '2026-09-17T10:00:00Z',
    );
  });

  it('demande les recommandations du site consulté à travers ses alertes', () => {
    const { fixture, getAlerts } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(of(SITE)),
        getCurrent: vi.fn().mockReturnValue(of(CURRENT_COMPLET)),
      },
      { getHistory: vi.fn().mockReturnValue(of([])) },
    );

    fixture.detectChanges();
    fixture.detectChanges();

    expect(getAlerts).toHaveBeenCalledWith({ site_id: 'SITE001' });
    expect(fixture.nativeElement.querySelector('app-recommendation-list')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Recommandations');
    expect(
      fixture.nativeElement.querySelector('a[href="/recommendations?site=SITE001"]'),
    ).not.toBeNull();
  });

  it("annonce l'absence de mesure sans interroger l'historique quand timestamp est null", () => {
    const getHistory = vi.fn().mockReturnValue(of([]));
    const { fixture } = setup(
      'SITE001',
      {
        getSite: vi.fn().mockReturnValue(of(SITE)),
        getCurrent: vi.fn().mockReturnValue(of(SANS_MESURE)),
      },
      { getHistory },
    );

    fixture.detectChanges();

    expect(getHistory).not.toHaveBeenCalled();
    expect(fixture.componentInstance.hasMeasurement()).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('Aucune mesure remontée pour ce site.');
  });
});
