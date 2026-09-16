import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { Dashboard } from './dashboard';
import { StatsService } from '../../core/services/stats.service';
import { AlertsService } from '../../core/services/alerts.service';

vi.mock('chart.js', () => {
  class ChartMock {
    update = vi.fn();
    destroy = vi.fn();
    data = { datasets: [{}] };
    static register = vi.fn();
  }
  return { Chart: ChartMock, registerables: [] };
});

describe('Dashboard', () => {
  afterEach(() => vi.useRealTimers());

  it('charge les stats et les alertes au démarrage', async () => {
    const statsMock = { getSummary: vi.fn().mockReturnValue(of({ total_sites: 7, sites: [] })) };
    const alertsMock = { getAlerts: vi.fn().mockReturnValue(of([{ alert_id: 'A1' }])) };

    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: StatsService, useValue: statsMock },
        { provide: AlertsService, useValue: alertsMock },
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();

    // laisse le timer(0, ...) se déclencher avant de vérifier
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();

    expect(statsMock.getSummary).toHaveBeenCalled();
    expect(alertsMock.getAlerts).toHaveBeenCalled();
    expect(fixture.componentInstance.alerts().length).toBe(1);
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it('signale l\'indisponibilité puis repart au rafraîchissement suivant', () => {
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
      ],
    });

    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();

    expect(fixture.componentInstance.alerts().length).toBe(0);
  });
});
