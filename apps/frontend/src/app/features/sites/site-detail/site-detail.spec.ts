import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { SiteDetail } from './site-detail';
import { SitesService } from '../../../core/services/sites.service';
import { ReadingsService } from '../../../core/services/readings.service';

const SITE = {
  site_id: 'SITE001',
  site_name: 'Site 1',
  site_type: 'industriel',
  location: 'Nantes',
  capacity_kw: 500,
  status: 'actif',
};

const READING_COMPLETE = {
  reading_id: 1,
  site_id: 'SITE001',
  timestamp: '2026-09-17T10:00:00Z',
  source: 'api_current' as const,
  consumption_kw: 120,
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
  TestBed.configureTestingModule({
    imports: [SiteDetail],
    providers: [
      provideRouter([]),
      { provide: ActivatedRoute, useValue: { paramMap } },
      { provide: SitesService, useValue: sitesMock },
      { provide: ReadingsService, useValue: readingsMock },
    ],
  });
  return { fixture: TestBed.createComponent(SiteDetail), paramMap };
}

describe('SiteDetail', () => {
  it('charge le site, la dernière lecture et son historique au démarrage', () => {
    const { fixture } = setup(
      'SITE001',
      { getSite: vi.fn().mockReturnValue(of(SITE)) },
      {
        getLatest: vi.fn().mockReturnValue(of(READING_COMPLETE)),
        getHistory: vi.fn().mockReturnValue(of([READING_COMPLETE])),
      },
    );

    fixture.detectChanges();

    expect(fixture.componentInstance.site()?.site_id).toBe('SITE001');
    expect(fixture.componentInstance.latestReading()?.consumption_kw).toBe(120);
    expect(fixture.componentInstance.history().length).toBe(1);
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it("signale l'indisponibilité quand un des appels échoue", () => {
    const { fixture } = setup(
      'SITE001',
      { getSite: vi.fn().mockReturnValue(throwError(() => new Error('nope'))) },
      {
        getLatest: vi.fn().mockReturnValue(of(READING_COMPLETE)),
        getHistory: vi.fn().mockReturnValue(of([])),
      },
    );

    fixture.detectChanges();

    expect(fixture.componentInstance.error()).not.toBeNull();
    expect(fixture.componentInstance.site()).toBeNull();
  });

  it('affiche explicitement les champs null avec leur raison plutôt que de les masquer', () => {
    const readingPartielle = {
      ...READING_COMPLETE,
      voltage_v: null,
      current_a: null,
      power_factor: null,
      null_reasons: ['electrical_sensor_failure'],
    };
    const { fixture } = setup(
      'SITE001',
      { getSite: vi.fn().mockReturnValue(of(SITE)) },
      {
        getLatest: vi.fn().mockReturnValue(of(readingPartielle)),
        getHistory: vi.fn().mockReturnValue(of([readingPartielle])),
      },
    );

    fixture.detectChanges();

    const tension = fixture.componentInstance
      .metrics()
      .find((m) => m.key === 'voltage_v');
    expect(tension?.value).toBeNull();
    expect(tension?.reason).toBe('capteur électrique en panne');

    const html = fixture.nativeElement.textContent;
    expect(html).toContain('Indisponible');
    expect(html).toContain('capteur électrique en panne');
  });

  it('recharge les données quand le paramètre de route siteId change', () => {
    const getSite = vi.fn().mockReturnValue(of(SITE));
    const { fixture, paramMap } = setup(
      'SITE001',
      { getSite },
      {
        getLatest: vi.fn().mockReturnValue(of(READING_COMPLETE)),
        getHistory: vi.fn().mockReturnValue(of([])),
      },
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
      { getSite: vi.fn().mockReturnValue(of(SITE)) },
      { getLatest: vi.fn().mockReturnValue(of(READING_COMPLETE)), getHistory },
    );

    fixture.detectChanges();

    expect(getHistory).toHaveBeenCalledWith(
      'SITE001',
      '2026-09-16T10:00:00.000Z',
      '2026-09-17T10:00:00Z',
    );
  });

  it("ne fixe aucune fenêtre d'historique quand le site n'a aucune lecture", () => {
    const getHistory = vi.fn().mockReturnValue(of([]));
    const { fixture } = setup(
      'SITE001',
      { getSite: vi.fn().mockReturnValue(of(SITE)) },
      { getLatest: vi.fn().mockReturnValue(of(null)), getHistory },
    );

    fixture.detectChanges();

    expect(getHistory).toHaveBeenCalledWith('SITE001', undefined, undefined);
    expect(fixture.componentInstance.latestReading()).toBeNull();
  });
});
