import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AlertsService } from './alerts.service';
import { environment } from '../../../environments/environment';

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

  it("appelle le bon endpoint et retourne un tableau d'alertes", () => {
    let result: unknown;
    service.getAlerts().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${environment.apiUrl}/alerts`);
    expect(req.request.method).toBe('GET');

    req.flush([
      {
        alert_id: 'ALR-TEST-1',
        timestamp: '2026-09-15T12:00:00',
        site_id: 'SITE001',
        severity: 'high',
        type: 'threshold',
        message: 'Test',
        value: 100,
        threshold: 90,
      },
    ]);

    expect((result as unknown[]).length).toBe(1);
  });
});
