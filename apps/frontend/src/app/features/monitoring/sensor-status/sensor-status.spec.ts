import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { SensorStatusView } from './sensor-status';
import { SensorsService } from '../../../core/services/sensors.service';
import { SiteSensors } from '../../../shared/models/sensor-status.model';
import {provideRouter} from '@angular/router';

const OK_SENSORS: SiteSensors = {
  consumption: { status: 'ok', since: null },
  electrical: { status: 'ok', since: null },
  temperature: { status: 'ok', since: null },
  humidity: { status: 'ok', since: null },
  network: { status: 'ok', since: null },
};

describe('SensorStatusView', () => {
  let sensorsMock: { getStatus: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    sensorsMock = { getStatus: vi.fn() };

    TestBed.configureTestingModule({
      imports: [SensorStatusView],
      providers: [
        { provide: SensorsService, useValue: sensorsMock },
        provideRouter([]),
      ],
    });
  });

  it('charge et affiche les données au démarrage', () => {
    sensorsMock.getStatus.mockReturnValue(
      of({
        timestamp: '2026-09-18T08:00:00',
        sites: [
          { site_id: 'SITE001', site_name: 'Bureau Test', overall: 'ok', sensors: OK_SENSORS },
        ],
      })
    );

    const fixture = TestBed.createComponent(SensorStatusView);
    fixture.detectChanges();

    expect(fixture.componentInstance.data()?.sites.length).toBe(1);
    expect(fixture.componentInstance.error()).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Bureau Test');
  });

  it("affiche un message d'erreur si l'appel échoue", () => {
    sensorsMock.getStatus.mockReturnValue(throwError(() => new Error('boom')));

    const fixture = TestBed.createComponent(SensorStatusView);
    fixture.detectChanges();

    expect(fixture.componentInstance.error()).toBe(
      'État des capteurs indisponible, réessayez plus tard.'
    );
    expect(fixture.componentInstance.data()).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('État des capteurs indisponible');
  });

  it('associe le bon ton de badge à chaque statut global', () => {
    sensorsMock.getStatus.mockReturnValue(of({ timestamp: '2026-09-18T08:00:00', sites: [] }));
    const fixture = TestBed.createComponent(SensorStatusView);
    const component = fixture.componentInstance;

    expect(component.badgeToneForOverall('ok')).toBe('success');
    expect(component.badgeToneForOverall('degraded')).toBe('warning');
    expect(component.badgeToneForOverall('critical')).toBe('critical');
    expect(component.badgeToneForOverall('inconnu')).toBe('neutral');
  });

  it('retourne le bon diagnostic via sensorOf', () => {
    sensorsMock.getStatus.mockReturnValue(of({ timestamp: '2026-09-18T08:00:00', sites: [] }));
    const fixture = TestBed.createComponent(SensorStatusView);
    const component = fixture.componentInstance;

    expect(component.sensorOf(OK_SENSORS, 'temperature')).toEqual({ status: 'ok', since: null });
  });

  it('affiche la date depuis quand un capteur est en panne', () => {
  const sensors: SiteSensors = {
    ...OK_SENSORS,
    temperature: { status: 'failing', since: '2026-09-18T08:00:00' },
  };
  sensorsMock.getStatus.mockReturnValue(
    of({
      timestamp: '2026-09-18T08:00:00',
      sites: [{ site_id: 'SITE001', site_name: 'Bureau Test', overall: 'degraded', sensors }],
    })
  );

  const fixture = TestBed.createComponent(SensorStatusView);
  fixture.detectChanges();

  expect(fixture.nativeElement.textContent).toContain('depuis');
  });
});
