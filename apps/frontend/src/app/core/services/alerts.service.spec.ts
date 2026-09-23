import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AlertsService } from './alerts.service';
import { environment } from '../../../environments/environment';
import { Alert } from '../../shared/models/alert.model';

const ALERT_API: Alert = {
  alert_id: 1,
  site_id: 'site-1',
  timestamp: '2026-09-16T00:00:00Z',
  type: 'threshold',
  severity: 'high',
  message: 'Dépassement du seuil configuré',
  value: 812.5,
  threshold: 720.0,
  metric: 'consumption_kw',
  prediction_id: null,
};

describe('AlertsService', () => {
  let service: AlertsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AlertsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it("appelle le bon endpoint sans paramètre et retourne un tableau d'alertes", () => {
    let result: Alert[] = [];
    service.getAlerts().subscribe((r) => (result = r));

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/alerts` && r.method === 'GET',
    );
    expect(req.request.params.keys()).toEqual([]);
    req.flush([ALERT_API]);

    expect(result.length).toBe(1);
    expect(result[0].alert_id).toBe(1);
    expect(result[0].prediction_id).toBeNull();
  });

  it('transmet les filtres site_id et severity en paramètres de requête', () => {
    service.getAlerts({ site_id: 'SITE001', severity: 'high' }).subscribe();

    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/alerts`);
    expect(req.request.params.get('site_id')).toBe('SITE001');
    expect(req.request.params.get('severity')).toBe('high');
    req.flush([]);
  });

  it('ne pose pas de paramètre pour un filtre omis', () => {
    service.getAlerts({ site_id: 'SITE001' }).subscribe();

    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/alerts`);
    expect(req.request.params.has('severity')).toBe(false);
    req.flush([]);
  });
});
