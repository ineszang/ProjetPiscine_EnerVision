import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { Dashboard } from './dashboard';
import { StatsService } from '../../core/services/stats.service';
import { AlertsService } from '../../core/services/alerts.service';
import { PredictionsService } from '../../core/services/predictions.service';
import {AuthService} from '../../core/services/auth.service';
import {Router, provideRouter} from '@angular/router';

vi.mock('chart.js', () => {
  class ChartMock {
    update = vi.fn();
    destroy = vi.fn();
    data = { datasets: [{}] };
    static register = vi.fn();
  }
  return { Chart: ChartMock, registerables: [] };
});

function predictionsMock(sites: unknown[] = []) {
  return { getPredictions: vi.fn().mockReturnValue(of({ timestamp: '2026-09-18T09:00:00Z', sites })) };
}

describe('Dashboard', () => {
  afterEach(() => vi.useRealTimers());

  it('charge les stats, les alertes et les prévisions au démarrage', async () => {
    const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
    const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([{ alert_id: 'A1' }])) };
    const predictions = predictionsMock([{ site_id: 'SITE001', site_name: 'Test', prediction: null }]);

    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: StatsService, useValue: statsMock },
        { provide: AlertsService, useValue: alertsMock },
        { provide: PredictionsService, useValue: predictions },
        provideRouter([]),
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();

    // laisse le timer(0, ...) se déclencher avant de vérifier
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();

    expect(statsMock.getSummary).toHaveBeenCalled();
    expect(alertsMock.getAlerts).toHaveBeenCalled();
    expect(predictions.getPredictions).toHaveBeenCalled();
    expect(fixture.componentInstance.alerts().length).toBe(1);
    expect(fixture.componentInstance.predictions().length).toBe(1);
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it("signale l'indisponibilité puis repart au rafraîchissement suivant", () => {
    vi.useFakeTimers();
    const statsMock = {
      getSummary: vi
        .fn()
        .mockReturnValueOnce(throwError(() => new Error('API injoignable')))
        .mockReturnValue(of({ total_sites: 7, sites: [] })),
    };
    const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([])) };

    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: StatsService, useValue: statsMock },
        { provide: AlertsService, useValue: alertsMock },
        { provide: PredictionsService, useValue: predictionsMock() },
        provideRouter([]),
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();

    vi.advanceTimersByTime(1);
    expect(statsMock.getSummary).toHaveBeenCalledTimes(1);
    expect(fixture.componentInstance.error()).not.toBeNull();
    expect(fixture.componentInstance.stats()).toBeNull();

    vi.advanceTimersByTime(10000);
    expect(statsMock.getSummary).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.stats()).not.toBeNull();
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it("n'interrompt pas la page quand le chargement des alertes échoue", () => {
    const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
    const alertsMock = { getAlerts: vi.fn().mockReturnValue(throwError(() => new Error('nope'))) };

    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: StatsService, useValue: statsMock },
        { provide: AlertsService, useValue: alertsMock },
        { provide: PredictionsService, useValue: predictionsMock() },
        provideRouter([]),
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();

    expect(fixture.componentInstance.alerts().length).toBe(0);
  });

  it("n'interrompt pas la page quand le chargement des prévisions échoue", () => {
    const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
    const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([])) };
    const predictions = {
      getPredictions: vi.fn().mockReturnValue(throwError(() => new Error('nope'))),
    };

    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: StatsService, useValue: statsMock },
        { provide: AlertsService, useValue: alertsMock },
        { provide: PredictionsService, useValue: predictions },
        provideRouter([]),
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();

    expect(fixture.componentInstance.predictions().length).toBe(0);
    expect(fixture.componentInstance.error()).not.toBeNull();
  });

  it('appelle logout et redirige vers /login au clic sur le bouton de déconnexion', () => {
  const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
  const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([])) };
  const authMock = { logout: vi.fn().mockReturnValue(of(undefined)), clearSession: vi.fn() };

  TestBed.configureTestingModule({
    imports: [Dashboard],
    providers: [
      { provide: StatsService, useValue: statsMock },
      { provide: AlertsService, useValue: alertsMock },
      { provide: PredictionsService, useValue: predictionsMock() },
      { provide: AuthService, useValue: authMock },
      provideRouter([]),
    ],
  });

  const fixture = TestBed.createComponent(Dashboard);
  fixture.detectChanges();

  const router = TestBed.inject(Router);
  const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

  const button = fixture.nativeElement.querySelector('.logout-button');
  button.click();

  expect(authMock.logout).toHaveBeenCalled();
  expect(navigateSpy).toHaveBeenCalledWith(['/login']);
  });
  it('déconnecte localement et redirige vers /login même si logout échoue côté réseau', () => {
  const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
  const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([])) };
  const authMock = {
    logout: vi.fn().mockReturnValue(throwError(() => new Error('réseau indisponible'))),
    clearSession: vi.fn(),
  };
  TestBed.configureTestingModule({
    imports: [Dashboard],
    providers: [
      { provide: StatsService, useValue: statsMock },
      { provide: AlertsService, useValue: alertsMock },
      { provide: PredictionsService, useValue: predictionsMock() },
      { provide: AuthService, useValue: authMock },
      provideRouter([]),
    ],
  });

  const fixture = TestBed.createComponent(Dashboard);
  fixture.detectChanges();

  const router = TestBed.inject(Router);
  const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

  const button = fixture.nativeElement.querySelector('.logout-button');
  button.click();

  expect(authMock.clearSession).toHaveBeenCalled();
  expect(navigateSpy).toHaveBeenCalledWith(['/login']);
});

  it('distingue le ton des sévérités high et critical', () => {
    const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
    const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([])) };

    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: StatsService, useValue: statsMock },
        { provide: AlertsService, useValue: alertsMock },
        { provide: PredictionsService, useValue: predictionsMock() },
        provideRouter([]),
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    const dashboard = fixture.componentInstance;

    expect(dashboard.badgeToneForSeverity('low')).toBe('success');
    expect(dashboard.badgeToneForSeverity('medium')).toBe('warning');
    expect(dashboard.badgeToneForSeverity('high')).toBe('danger');
    expect(dashboard.badgeToneForSeverity('critical')).toBe('critical');
    expect(dashboard.badgeToneForSeverity('high')).not.toBe(
      dashboard.badgeToneForSeverity('critical'),
    );
  });

  it('distingue le ton des statuts de prévision', () => {
    const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
    const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([])) };

    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: StatsService, useValue: statsMock },
        { provide: AlertsService, useValue: alertsMock },
        { provide: PredictionsService, useValue: predictionsMock() },
        provideRouter([]),
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    const dashboard = fixture.componentInstance;

    expect(dashboard.badgeToneForPredictionStatus('available')).toBe('success');
    expect(dashboard.badgeToneForPredictionStatus('insufficient_data')).toBe('warning');
    expect(dashboard.badgeToneForPredictionStatus('error')).toBe('danger');
  });
});
