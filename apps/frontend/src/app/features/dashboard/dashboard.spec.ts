import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { Observable, of, throwError } from 'rxjs';
import { Router, provideRouter } from '@angular/router';
import { Dashboard } from './dashboard';
import { StatsService } from '../../core/services/stats.service';
import { AlertsService } from '../../core/services/alerts.service';
import { SitesService } from '../../core/services/sites.service';
import { PredictionsService } from '../../core/services/predictions.service';
import { AuthService } from '../../core/services/auth.service';

vi.mock('chart.js', () => {
  class ChartMock {
    update = vi.fn();
    destroy = vi.fn();
    data = { datasets: [{}] };
    static register = vi.fn();
  }
  return { Chart: ChartMock, registerables: [] };
});

const STATS = { total_sites: 7, sites: [] };

function predictionsMock(sites: unknown[] = []) {
  return {
    getPredictions: vi.fn().mockReturnValue(of({ timestamp: '2026-09-18T09:00:00Z', sites })),
  };
}

function setup(
  options: {
    stats?: Observable<unknown>;
    predictions?: { getPredictions: ReturnType<typeof vi.fn> };
    auth?: Record<string, unknown>;
  } = {},
) {
  const statsMock = { getSummary: vi.fn().mockReturnValue(options.stats ?? of(STATS)) };
  const predictions = options.predictions ?? predictionsMock();
  TestBed.configureTestingModule({
    imports: [Dashboard],
    providers: [
      { provide: StatsService, useValue: statsMock },
      { provide: AlertsService, useValue: { getAlerts: vi.fn().mockReturnValue(of([])) } },
      { provide: SitesService, useValue: { getSites: vi.fn().mockReturnValue(of([])) } },
      { provide: PredictionsService, useValue: predictions },
      ...(options.auth ? [{ provide: AuthService, useValue: options.auth }] : []),
      provideRouter([]),
    ],
  });
  return { fixture: TestBed.createComponent(Dashboard), statsMock, predictions };
}

describe('Dashboard', () => {
  afterEach(() => vi.useRealTimers());

  it('charge les stats et les prévisions au démarrage', async () => {
    const { fixture, statsMock, predictions } = setup({
      predictions: predictionsMock([{ site_id: 'SITE001', site_name: 'Test', prediction: null }]),
    });

    fixture.detectChanges();
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();

    expect(statsMock.getSummary).toHaveBeenCalled();
    expect(predictions.getPredictions).toHaveBeenCalled();
    expect(fixture.componentInstance.predictions().length).toBe(1);
    expect(fixture.componentInstance.statsError()).toBeNull();
    expect(fixture.componentInstance.predictionsError()).toBeNull();
  });

  it('délègue les alertes au widget app-alert-feed', () => {
    const { fixture } = setup();

    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-alert-feed')).not.toBeNull();
  });

  it("signale l'indisponibilité puis repart au rafraîchissement suivant", () => {
    vi.useFakeTimers();
    const { fixture, statsMock } = setup({
      stats: throwError(() => new Error('API injoignable')),
    });
    statsMock.getSummary
      .mockReturnValueOnce(throwError(() => new Error('API injoignable')))
      .mockReturnValue(of(STATS));

    fixture.detectChanges();

    vi.advanceTimersByTime(1);
    expect(statsMock.getSummary).toHaveBeenCalledTimes(1);
    expect(fixture.componentInstance.statsError()).not.toBeNull();
    expect(fixture.componentInstance.stats()).toBeNull();

    vi.advanceTimersByTime(10000);
    expect(statsMock.getSummary).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.stats()).not.toBeNull();
    expect(fixture.componentInstance.statsError()).toBeNull();
  });

  it("n'interrompt pas la page quand le chargement des prévisions échoue", () => {
    const { fixture } = setup({
      predictions: { getPredictions: vi.fn().mockReturnValue(throwError(() => new Error('nope'))) },
    });

    fixture.detectChanges();

    expect(fixture.componentInstance.predictions().length).toBe(0);
    expect(fixture.componentInstance.predictionsError()).not.toBeNull();
  });

  it("un rafraîchissement de stats n'efface pas une erreur de prévisions en attente", () => {
    vi.useFakeTimers();
    const { fixture } = setup({
      predictions: { getPredictions: vi.fn().mockReturnValue(throwError(() => new Error('nope'))) },
    });

    fixture.detectChanges();
    expect(fixture.componentInstance.predictionsError()).not.toBeNull();

    // Plusieurs cycles de `timer(0, 10_000)` (stats) plus tard, l'erreur des prévisions doit
    // toujours être visible : rien ne vient la rafraîchir tant que la section n'est pas rechargée.
    vi.advanceTimersByTime(30000);

    expect(fixture.componentInstance.predictionsError()).not.toBeNull();
    expect(fixture.componentInstance.statsError()).toBeNull();
  });

  it('appelle logout et redirige vers /login au clic sur le bouton de déconnexion', () => {
    const authMock = {
      logout: vi.fn().mockReturnValue(of(undefined)),
      clearSession: vi.fn(),
      principal: vi.fn().mockReturnValue({ role: 'admin' }),
    };
    const { fixture } = setup({ auth: authMock });
    fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    fixture.nativeElement.querySelector('.logout-button').click();

    expect(authMock.logout).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith(['/login']);
  });

  it('déconnecte localement et redirige vers /login même si logout échoue côté réseau', () => {
    const authMock = {
      logout: vi.fn().mockReturnValue(throwError(() => new Error('réseau indisponible'))),
      clearSession: vi.fn(),
      principal: vi.fn().mockReturnValue({ role: 'admin' }),
    };
    const { fixture } = setup({ auth: authMock });
    fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    fixture.nativeElement.querySelector('.logout-button').click();

    expect(authMock.clearSession).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith(['/login']);
  });

  it('affiche l’heure du dernier relevé et les indicateurs du parc', () => {
    vi.useFakeTimers();
    const { fixture } = setup({
      stats: of({
        timestamp: '2026-09-18T09:00:00Z',
        total_sites: 7,
        total_consumption_kw: 1234.5,
        total_capacity_kw: 5000,
        average_load_percent: 24.7,
        sites: [],
      }),
    });

    fixture.detectChanges();
    vi.advanceTimersByTime(1);
    fixture.detectChanges();

    const texte = fixture.nativeElement.textContent as string;
    expect(texte).toContain('Actualisé à');
    expect(texte).toContain('7 sites suivis');
    expect(texte).toContain('Marge confortable');
    expect(fixture.nativeElement.querySelector('.progress-bar__fill--success')).not.toBeNull();
  });

  it('présente les prévisions en tableau avec un lien vers chaque site', () => {
    const { fixture } = setup({
      predictions: predictionsMock([
        {
          site_id: 'SITE001',
          site_name: 'Usine Nantes',
          prediction: {
            target_at: '2026-09-18T10:00:00Z',
            target_metric: 'consumption_kwh',
            period_minutes: 60,
            predicted_value: 118.4,
            status: 'available',
            failure_reason: null,
            model_reference: 'lightgbm-v1',
            created_at: '2026-09-18T09:00:00Z',
          },
        },
        { site_id: 'SITE002', site_name: 'Bureau Lille', prediction: null },
      ]),
    });

    fixture.detectChanges();

    const table = fixture.nativeElement.querySelector('table.ev-table');
    expect(table).not.toBeNull();
    expect(table.textContent).toContain('118.4 kWh');
    expect(table.textContent).toContain('Pas encore de prévision');
    expect(fixture.nativeElement.querySelector('a[href="/sites/SITE001"]')).not.toBeNull();
  });

  it('colore la charge moyenne selon les seuils 70 % et 90 %', () => {
    const { fixture } = setup();
    const dashboard = fixture.componentInstance;

    expect(dashboard.loadTone(69.9)).toBe('success');
    expect(dashboard.loadTone(70)).toBe('warning');
    expect(dashboard.loadTone(89.9)).toBe('warning');
    expect(dashboard.loadTone(90)).toBe('danger');
    expect(dashboard.loadHint(95)).toBe('Proche de la capacité du parc');
  });

  it('distingue le ton des statuts de prévision', () => {
    const { fixture } = setup();
    const dashboard = fixture.componentInstance;

    expect(dashboard.badgeToneForPredictionStatus('available')).toBe('success');
    expect(dashboard.badgeToneForPredictionStatus('insufficient_data')).toBe('warning');
    expect(dashboard.badgeToneForPredictionStatus('error')).toBe('danger');
  });
});
